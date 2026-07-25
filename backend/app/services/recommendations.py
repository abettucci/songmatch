"""
Music recommendation engine — 4 algorithms.

All algorithms avoid deprecated/removed Spotify endpoints:
- NO get_audio_features (deprecated Nov 2024)
- NO get_artist_top_tracks (removed Feb 2026)
- NO track.getSimilar from Last.fm (broken since early 2025)

Candidate discovery: related-artists → albums → tracks (via Spotify)
Audio features: librosa (+ Cyanite.ai + Deezer enrichment where available)

Algorithms:
  lastfm:     Last.fm artist.getSimilar + artist.getTopTracks → Spotify search
  custom:     librosa content-based (energy, valence, tempo, MFCC, chroma)
  audio:      librosa MFCC cosine similarity
  structural: SSM + Foote novelty + Ward clustering (Martínez 2023)
"""

import asyncio
from typing import List, Dict, Any, Optional, Set
import logging

import numpy as np

from app.services.spotify import spotify_client
from app.services.lastfm import lastfm_client
from app.services.audio_analysis import audio_analyzer, AudioAnalysisResult
from app.services.audio_features import audio_extractor

logger = logging.getLogger(__name__)


class RecommendationEngine:
    ALGORITHM_LASTFM = "lastfm"
    ALGORITHM_CUSTOM = "custom"
    ALGORITHM_AUDIO = "audio"
    ALGORITHM_STRUCTURAL = "structural"
    ALGORITHM_CLAP = "clap"
    FILTER_DEFAULTS = {
        "energy": (0.0, 1.0),
        "valence": (0.0, 1.0),
        "danceability": (0.0, 1.0),
        "acousticness": (0.0, 1.0),
        "instrumentalness": (0.0, 1.0),
        "liveness": (0.0, 1.0),
        "speechiness": (0.0, 1.0),
        "tempo": (60.0, 200.0),
        "loudness": (-60.0, 0.0),
    }

    async def get_recommendations(
        self,
        seed_tracks: List[str],
        algorithm: str = ALGORITHM_LASTFM,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        feature_cache: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Get music recommendations based on seed Spotify track IDs.

        Returns dict with: recommendations, method, seed_tracks, algorithm_used, count
        """
        if not seed_tracks:
            return {"recommendations": [], "method": "none", "error": "No seed tracks provided"}

        seed_tracks = seed_tracks[:5]
        limit = max(1, min(50, limit))
        filters = filters or {}

        seed_track_info = await spotify_client.get_tracks(seed_tracks)
        if not seed_track_info:
            return {"recommendations": [], "method": "none", "error": "Could not fetch seed tracks"}

        # Build lookup sets using spotify_id (the field name from _format_track)
        seed_ids: Set[str] = {t["spotify_id"] for t in seed_track_info if t.get("spotify_id")}
        seed_artist_ids: Set[str] = {t["artist_id"] for t in seed_track_info if t.get("artist_id")}

        if algorithm == self.ALGORITHM_LASTFM:
            recs, method = await self._lastfm_recommendations(
                seed_track_info, limit, seed_ids, seed_artist_ids
            )
        elif algorithm == self.ALGORITHM_CUSTOM:
            recs, method = await self._custom_recommendations(
                seed_track_info, limit, seed_ids, seed_artist_ids, filters, feature_cache
            )
        elif algorithm == self.ALGORITHM_AUDIO:
            recs, method = await self._audio_recommendations(
                seed_track_info, limit, seed_ids, seed_artist_ids, feature_cache
            )
        elif algorithm == self.ALGORITHM_STRUCTURAL:
            recs, method = await self._structural_recommendations(
                seed_track_info, limit, seed_ids, seed_artist_ids, feature_cache
            )
        elif algorithm == self.ALGORITHM_CLAP:
            recs, method = await self._clap_recommendations(
                seed_track_info, limit, seed_ids, seed_artist_ids, feature_cache
            )
        else:
            recs, method = await self._lastfm_recommendations(
                seed_track_info, limit, seed_ids, seed_artist_ids
            )

        if self._has_active_audio_filters(filters):
            recs = await self._filter_recommendations_by_features(
                recs,
                filters,
                feature_cache,
                limit,
            )

        return {
            "recommendations": recs,
            "method": method,
            "seed_tracks": seed_track_info,
            "algorithm_used": algorithm,
            "count": len(recs),
        }

    # ──────────────────────────────────────────────────────
    # Algorithm 1: Last.fm collaborative filtering
    # ──────────────────────────────────────────────────────

    async def _lastfm_recommendations(
        self,
        seed_tracks: List[Dict[str, Any]],
        limit: int,
        seed_ids: Set[str],
        seed_artist_ids: Set[str],
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        1. For each seed: Last.fm artist.getSimilar → similar artists
        2. For each similar artist: Last.fm artist.getTopTracks → candidates
        3. Search each candidate in Spotify
        4. Deduplicate and rank by Last.fm match score
        """
        # Collect similar artists for all seeds in parallel
        similar_artist_tasks = [
            lastfm_client.get_similar_artists(track["artist"], limit=5)
            for track in seed_tracks
        ]
        similar_artist_results = await asyncio.gather(*similar_artist_tasks, return_exceptions=True)

        # Flatten similar artists, dedup by name
        seen_artists: Set[str] = {t["artist"].lower() for t in seed_tracks}
        similar_artists: List[Dict[str, Any]] = []
        for result in similar_artist_results:
            if isinstance(result, list):
                for a in result:
                    name = a.get("name", "").lower()
                    if name and name not in seen_artists:
                        seen_artists.add(name)
                        similar_artists.append(a)

        # Sort by match score and take top 8
        similar_artists.sort(key=lambda a: a.get("match", 0), reverse=True)
        similar_artists = similar_artists[:8]

        if not similar_artists:
            logger.warning("Last.fm returned no similar artists, falling back to custom")
            return await self._custom_recommendations(
                seed_tracks, limit, seed_ids, seed_artist_ids, {}, None
            )

        # Get top tracks for each similar artist in parallel
        top_track_tasks = [
            lastfm_client.get_artist_top_tracks(a["name"], limit=5)
            for a in similar_artists
        ]
        top_track_results = await asyncio.gather(*top_track_tasks, return_exceptions=True)

        # Build (artist, track_name, match_score) candidates
        candidates: List[Dict[str, Any]] = []
        for artist, result in zip(similar_artists, top_track_results):
            if isinstance(result, list):
                for track in result:
                    candidates.append({
                        "artist": artist["name"],
                        "name": track["name"],
                        "match_score": artist.get("match", 0),
                    })

        # Search Spotify for each candidate (limit concurrent to avoid rate limiting)
        recommendations: List[Dict[str, Any]] = []
        seen_rec_ids: Set[str] = set(seed_ids)
        seen_names: Set[str] = set()

        for candidate in candidates:
            if len(recommendations) >= limit:
                break

            key = f"{candidate['artist'].lower()}:{candidate['name'].lower()}"
            if key in seen_names:
                continue
            seen_names.add(key)

            spotify_track = await spotify_client.search_track(
                candidate["artist"], candidate["name"]
            )
            if not spotify_track:
                continue

            track_id = spotify_track.get("spotify_id")
            if not track_id or track_id in seen_rec_ids:
                continue
            if spotify_track.get("artist_id") in seed_artist_ids:
                continue

            seen_rec_ids.add(track_id)
            spotify_track["match_score"] = candidate["match_score"]
            spotify_track["source"] = "lastfm"
            recommendations.append(spotify_track)

        return recommendations, "lastfm_collaborative_filtering"

    # ──────────────────────────────────────────────────────
    # Algorithm 2: Custom content-based (librosa)
    # ──────────────────────────────────────────────────────

    async def _custom_recommendations(
        self,
        seed_tracks: List[Dict[str, Any]],
        limit: int,
        seed_ids: Set[str],
        seed_artist_ids: Set[str],
        filters: Dict[str, Any],
        feature_cache: Optional[Any] = None,
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        1. Extract librosa features from seed previews
        2. Compute average feature vector
        3. Get candidate tracks via related-artists → albums → tracks
        4. Extract librosa features from candidates (parallel, up to 15)
        5. Rank by cosine similarity on feature vector
        """
        # Extract features for seeds with preview_url
        seed_analyses = await self._extract_seed_features(seed_tracks, include_structure=False)
        if not seed_analyses:
            logger.warning("No seed previews available for custom algorithm")
            return [], "custom_no_seed_features"

        # Average seed feature vector
        vectors = [audio_extractor.to_feature_vector(a.audio_data) for a in seed_analyses if a.audio_data]
        if not vectors:
            return [], "custom_no_seed_vectors"
        seed_vector = np.mean(vectors, axis=0)

        # Get candidate tracks (require preview_url)
        candidates = await self._get_candidate_tracks(
            seed_tracks, seed_ids, seed_artist_ids, require_preview=True, max_total=40
        )
        if not candidates:
            return [], "custom_no_candidates"

        # Extract features for candidates in parallel (limit to 15)
        candidate_batch = candidates[:15]
        analysis_tasks = [
            audio_analyzer.analyze_from_url(
                t["preview_url"],
                include_structure=False,
                isrc=t.get("isrc"),
                spotify_id=t.get("spotify_id"),
            )
            for t in candidate_batch
        ]
        candidate_analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)

        # Score by cosine similarity
        scored: List[Dict[str, Any]] = []
        for track, analysis in zip(candidate_batch, candidate_analyses):
            if isinstance(analysis, AudioAnalysisResult) and analysis.audio_data:
                v = audio_extractor.to_feature_vector(analysis.audio_data)
                norm_seed = np.linalg.norm(seed_vector)
                norm_v = np.linalg.norm(v)
                if norm_seed > 0 and norm_v > 0:
                    score = float(np.dot(seed_vector, v) / (norm_seed * norm_v))
                    track["similarity_score"] = score
                    track["source"] = "custom"
                    await self._attach_and_cache_features(track, analysis, feature_cache)
                    scored.append(track)

        scored.sort(key=lambda t: t.get("similarity_score", 0), reverse=True)
        return scored[:limit], "custom_content_based_librosa"

    # ──────────────────────────────────────────────────────
    # Algorithm 3: Audio MFCC similarity
    # ──────────────────────────────────────────────────────

    async def _audio_recommendations(
        self,
        seed_tracks: List[Dict[str, Any]],
        limit: int,
        seed_ids: Set[str],
        seed_artist_ids: Set[str],
        feature_cache: Optional[Any] = None,
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Similar to custom but uses MFCC-only cosine similarity.
        """
        seed_analyses = await self._extract_seed_features(seed_tracks, include_structure=False)
        if not seed_analyses:
            logger.warning("No seed previews for audio algorithm")
            return await self._lastfm_recommendations(seed_tracks, limit, seed_ids, seed_artist_ids)

        candidates = await self._get_candidate_tracks(
            seed_tracks, seed_ids, seed_artist_ids, require_preview=True, max_total=40
        )
        if not candidates:
            return [], "audio_no_candidates"

        candidate_batch = candidates[:15]
        analysis_tasks = [
            audio_analyzer.analyze_from_url(
                t["preview_url"],
                include_structure=False,
                isrc=t.get("isrc"),
                spotify_id=t.get("spotify_id"),
            )
            for t in candidate_batch
        ]
        candidate_analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)

        scored: List[Dict[str, Any]] = []
        for track, cand_analysis in zip(candidate_batch, candidate_analyses):
            if not isinstance(cand_analysis, AudioAnalysisResult) or not cand_analysis.audio_data:
                continue
            scores = []
            for seed_a in seed_analyses:
                s = audio_analyzer.calculate_similarity(seed_a, cand_analysis, use_structure=False)
                scores.append(s)
            if scores:
                track["similarity_score"] = float(np.mean(scores))
                track["source"] = "audio_mfcc"
                await self._attach_and_cache_features(track, cand_analysis, feature_cache)
                scored.append(track)

        scored.sort(key=lambda t: t.get("similarity_score", 0), reverse=True)
        return scored[:limit], "audio_mfcc_analysis"

    # ──────────────────────────────────────────────────────
    # Algorithm 4: Structural (SSM + novelty + clustering)
    # ──────────────────────────────────────────────────────

    async def _structural_recommendations(
        self,
        seed_tracks: List[Dict[str, Any]],
        limit: int,
        seed_ids: Set[str],
        seed_artist_ids: Set[str],
        feature_cache: Optional[Any] = None,
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Full Martínez 2023 pipeline: SSM → Foote novelty → Ward clustering.
        Can take 10-30s depending on number of candidates.
        """
        seed_analyses = await self._extract_seed_features(seed_tracks, include_structure=True)
        structural_seeds = [a for a in seed_analyses if a.structural_analysis]
        if not structural_seeds:
            logger.warning("No structural analysis available, falling back to audio")
            return await self._audio_recommendations(
                seed_tracks, limit, seed_ids, seed_artist_ids, feature_cache
            )

        candidates = await self._get_candidate_tracks(
            seed_tracks, seed_ids, seed_artist_ids, require_preview=True, max_total=30
        )
        if not candidates:
            return [], "structural_no_candidates"

        candidate_batch = candidates[:12]
        analysis_tasks = [
            audio_analyzer.analyze_from_url(
                t["preview_url"],
                include_structure=True,
                isrc=t.get("isrc"),
                spotify_id=t.get("spotify_id"),
            )
            for t in candidate_batch
        ]
        candidate_analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)

        scored: List[Dict[str, Any]] = []
        for track, cand_analysis in zip(candidate_batch, candidate_analyses):
            if not isinstance(cand_analysis, AudioAnalysisResult) or not cand_analysis.structural_analysis:
                continue
            scores = []
            for seed_a in structural_seeds:
                s = audio_analyzer.calculate_similarity(seed_a, cand_analysis, use_structure=True)
                scores.append(s)
            if scores:
                track["similarity_score"] = float(np.mean(scores))
                track["structure_pattern"] = cand_analysis.structure_pattern
                track["n_sections"] = len(cand_analysis.sections)
                track["source"] = "structural_analysis"
                await self._attach_and_cache_features(track, cand_analysis, feature_cache)
                scored.append(track)

        scored.sort(key=lambda t: t.get("similarity_score", 0), reverse=True)
        return scored[:limit], "structural_analysis"

    # ──────────────────────────────────────────────────────
    # Algorithm 5: CLAP deep audio embeddings
    # ──────────────────────────────────────────────────────

    async def _clap_recommendations(
        self,
        seed_tracks: List[Dict[str, Any]],
        limit: int,
        seed_ids: Set[str],
        seed_artist_ids: Set[str],
        feature_cache: Optional[Any] = None,
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Deep learning audio similarity via CLAP (laion/larger_clap_music).

        1. Embed each seed preview → 512-dim L2-normalized vector
        2. Average seed embeddings, renormalize
        3. Get candidate tracks (same pipeline as custom/audio)
        4. Embed candidates, rank by cosine similarity (dot product since L2-normalized)

        Falls back to audio MFCC if torch/transformers is not installed or
        if seed previews are unavailable.
        """
        from app.services.clap_embeddings import clap_service

        seeds_with_preview = [t for t in seed_tracks if t.get("preview_url")]
        if not seeds_with_preview:
            logger.warning("No seed previews for CLAP algorithm, falling back to audio")
            return await self._audio_recommendations(
                seed_tracks, limit, seed_ids, seed_artist_ids, feature_cache
            )

        # Embed seeds in parallel
        seed_embed_tasks = [clap_service.embed_from_url(t["preview_url"]) for t in seeds_with_preview]
        seed_embeddings_raw = await asyncio.gather(*seed_embed_tasks, return_exceptions=True)
        valid_seeds = [e for e in seed_embeddings_raw if isinstance(e, np.ndarray)]

        if not valid_seeds:
            logger.warning("CLAP failed to embed seeds (torch not installed?), falling back to audio")
            return await self._audio_recommendations(
                seed_tracks, limit, seed_ids, seed_artist_ids, feature_cache
            )

        # Average seed embedding and renormalize
        mean_vec = np.mean(valid_seeds, axis=0)
        norm = np.linalg.norm(mean_vec)
        if norm > 0:
            mean_vec = mean_vec / norm

        # Discover candidates (require preview for embedding)
        candidates = await self._get_candidate_tracks(
            seed_tracks, seed_ids, seed_artist_ids, require_preview=True, max_total=40
        )
        if not candidates:
            return [], "clap_no_candidates"

        # Embed up to 20 candidates in parallel
        candidate_batch = candidates[:20]
        cand_embed_tasks = [clap_service.embed_from_url(t["preview_url"]) for t in candidate_batch]
        cand_embeddings_raw = await asyncio.gather(*cand_embed_tasks, return_exceptions=True)

        # Score: dot product = cosine similarity (both vectors are L2-normalized)
        scored: List[Dict[str, Any]] = []
        for track, embedding in zip(candidate_batch, cand_embeddings_raw):
            if not isinstance(embedding, np.ndarray):
                continue
            score = float(np.dot(mean_vec, embedding))
            track["similarity_score"] = score
            track["source"] = "clap_embedding"
            scored.append(track)

        scored.sort(key=lambda t: t.get("similarity_score", 0), reverse=True)
        return scored[:limit], "clap_deep_audio_embeddings"

    # ──────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────

    async def _extract_seed_features(
        self,
        seed_tracks: List[Dict[str, Any]],
        include_structure: bool = False,
    ) -> List[AudioAnalysisResult]:
        """Extract features for seed tracks that have preview_url."""
        tasks = []
        for track in seed_tracks:
            preview_url = track.get("preview_url")
            if preview_url:
                tasks.append(
                    audio_analyzer.analyze_from_url(
                        preview_url,
                        include_structure=include_structure,
                        isrc=track.get("isrc"),
                        spotify_id=track.get("spotify_id"),
                    )
                )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, AudioAnalysisResult) and r.audio_data]

    async def _attach_and_cache_features(
        self,
        track: Dict[str, Any],
        analysis: AudioAnalysisResult,
        feature_cache: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        if not analysis or not analysis.audio_data:
            return None

        features = analysis.to_dict().get("audio_features", {})
        features["feature_vector"] = audio_extractor.to_feature_vector(analysis.audio_data).tolist()
        track["audio_features"] = features

        if feature_cache and track.get("spotify_id"):
            try:
                await feature_cache.upsert(
                    spotify_id=track["spotify_id"],
                    isrc=track.get("isrc"),
                    provider=features.get("source", "librosa"),
                    status="finished",
                    features=features,
                )
            except Exception as e:
                logger.debug(f"Failed to cache audio features for {track.get('spotify_id')}: {e}")

        return features

    async def _get_track_features(
        self,
        track: Dict[str, Any],
        feature_cache: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        if track.get("audio_features"):
            return track["audio_features"]

        spotify_id = track.get("spotify_id")
        if feature_cache and spotify_id:
            try:
                cached = await feature_cache.get_by_spotify_id(spotify_id)
                if cached and cached.status == "finished" and cached.features:
                    track["audio_features"] = cached.features
                    return cached.features
            except Exception as e:
                logger.debug(f"Failed to read cached audio features for {spotify_id}: {e}")

        preview_url = track.get("preview_url")
        if not preview_url:
            return None

        analysis = await audio_analyzer.analyze_from_url(
            preview_url,
            include_structure=False,
            isrc=track.get("isrc"),
            spotify_id=spotify_id,
        )
        if not isinstance(analysis, AudioAnalysisResult):
            return None

        return await self._attach_and_cache_features(track, analysis, feature_cache)

    def _has_active_audio_filters(self, filters: Optional[Dict[str, Any]]) -> bool:
        if not filters or filters.get("use_filters") is False:
            return False

        enabled = filters.get("enabled_filters") or {}
        for field, (default_min, default_max) in self.FILTER_DEFAULTS.items():
            if enabled.get(field) is False:
                continue
            min_value = float(filters.get(f"min_{field}", default_min))
            max_value = float(filters.get(f"max_{field}", default_max))
            if min_value > default_min or max_value < default_max:
                return True
        return False

    def _passes_feature_filters(
        self,
        features: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> bool:
        enabled = filters.get("enabled_filters") or {}
        for field, (default_min, default_max) in self.FILTER_DEFAULTS.items():
            if enabled.get(field) is False:
                continue

            min_value = float(filters.get(f"min_{field}", default_min))
            max_value = float(filters.get(f"max_{field}", default_max))
            if min_value <= default_min and max_value >= default_max:
                continue

            raw_value = features.get(field)
            if raw_value is None:
                return False

            value = float(raw_value)
            if value < min_value or value > max_value:
                return False
        return True

    async def _filter_recommendations_by_features(
        self,
        recommendations: List[Dict[str, Any]],
        filters: Dict[str, Any],
        feature_cache: Optional[Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []

        for track in recommendations:
            features = await self._get_track_features(track, feature_cache)
            if features and self._passes_feature_filters(features, filters):
                filtered.append(track)
            if len(filtered) >= limit:
                break

        return filtered

    async def _get_candidate_tracks(
        self,
        seed_tracks: List[Dict[str, Any]],
        seed_ids: Set[str],
        seed_artist_ids: Set[str],
        require_preview: bool = False,
        max_total: int = 40,
    ) -> List[Dict[str, Any]]:
        """
        Discover candidates without using deprecated top-tracks endpoint.
        Strategy: related-artists → recent albums → album tracks
        """
        candidates: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set(seed_ids)

        artist_ids = list({t["artist_id"] for t in seed_tracks if t.get("artist_id")})

        # Get related artists for all seed artists in parallel
        related_tasks = [spotify_client.get_related_artists(aid) for aid in artist_ids[:3]]
        related_results = await asyncio.gather(*related_tasks, return_exceptions=True)

        related_artist_ids: List[str] = []
        for result in related_results:
            if isinstance(result, list):
                for a in result[:5]:
                    if a.get("id") and a["id"] not in seed_artist_ids:
                        related_artist_ids.append(a["id"])

        # Deduplicate related artists
        related_artist_ids = list(dict.fromkeys(related_artist_ids))[:10]

        # Get albums for related artists in parallel
        album_tasks = [
            spotify_client.get_artist_albums(aid, limit=3)
            for aid in related_artist_ids[:8]
        ]
        album_results = await asyncio.gather(*album_tasks, return_exceptions=True)

        album_ids: List[str] = []
        for result in album_results:
            if isinstance(result, list):
                for album in result[:2]:
                    if album.get("id"):
                        album_ids.append(album["id"])

        # Get tracks from albums in parallel
        track_tasks = [
            spotify_client.get_album_tracks(aid, limit=5)
            for aid in album_ids[:15]
        ]
        track_results = await asyncio.gather(*track_tasks, return_exceptions=True)

        for result in track_results:
            if not isinstance(result, list):
                continue
            for raw_track in result:
                if len(candidates) >= max_total:
                    break
                track_id = raw_track.get("id")
                if not track_id or track_id in seen_ids:
                    continue
                # Fetch full track info to get preview_url and other fields
                full_track = await spotify_client.get_track(track_id)
                if not full_track:
                    continue
                if require_preview and not full_track.get("preview_url"):
                    continue
                seen_ids.add(track_id)
                candidates.append(full_track)

        return candidates


recommendation_engine = RecommendationEngine()
