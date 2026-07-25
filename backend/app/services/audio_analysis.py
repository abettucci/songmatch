"""
Unified Audio Analysis Service.

Coordinates feature extraction (librosa + Cyanite + Deezer) and structural
analysis (SSM, novelty, clustering) for a given audio preview URL.

CPU-bound work runs in a ThreadPoolExecutor to avoid blocking the event loop.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Any

from app.services.audio_features import AudioData, audio_extractor
from app.services.structural_analysis import (
    StructuralAnalysis,
    MusicStructureAnalyzer,
    music_structure_analyzer,
)

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)


class AudioAnalysisResult:
    """Combines feature extraction + structural analysis results."""

    def __init__(
        self,
        audio_data: Optional[AudioData] = None,
        structural_analysis: Optional[StructuralAnalysis] = None,
    ):
        self.audio_data = audio_data
        self.structural_analysis = structural_analysis

    @property
    def sections(self) -> List[Dict[str, Any]]:
        if self.structural_analysis:
            return [
                {
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration": s.duration,
                    "cluster_id": s.cluster_id,
                    "label": s.label,
                    "loudness": s.loudness,
                }
                for s in self.structural_analysis.sections
            ]
        return []

    @property
    def structure_pattern(self) -> str:
        if self.structural_analysis and self.structural_analysis.sections:
            labels = "ABCDEFGHIJ"
            return "".join(
                labels[s.cluster_id]
                for s in self.structural_analysis.sections
                if 0 <= s.cluster_id < len(labels)
            )
        return ""

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "sections": self.sections,
            "structure_pattern": self.structure_pattern,
        }
        if self.audio_data:
            result["audio_features"] = {
                "tempo": self.audio_data.tempo,
                "energy": self.audio_data.energy,
                "valence": self.audio_data.valence,
                "danceability": self.audio_data.danceability,
                "acousticness": self.audio_data.acousticness,
                "instrumentalness": self.audio_data.instrumentalness,
                "speechiness": self.audio_data.speechiness,
                "liveness": self.audio_data.liveness,
                "loudness": self.audio_data.loudness,
                "duration": self.audio_data.duration,
                "arousal": self.audio_data.arousal,
                "key": self.audio_data.key,
                "time_signature": self.audio_data.time_signature,
                "source": self.audio_data.feature_source,
                "genre_tags": self.audio_data.genre_tags,
                "subgenre_tags": self.audio_data.subgenre_tags,
                "mood_tags": self.audio_data.mood_tags,
                "movement_tags": self.audio_data.movement_tags,
                "character_tags": self.audio_data.character_tags,
                "instrument_tags": self.audio_data.instrument_tags,
                "voice_tags": self.audio_data.voice_tags,
                "transformer_caption": self.audio_data.transformer_caption,
            }
        if self.structural_analysis:
            result["n_sections"] = len(self.structural_analysis.sections)
            result["n_clusters"] = self.structural_analysis.n_clusters
            result["silhouette_score"] = self.structural_analysis.silhouette_score
        return result


def _run_structural_analysis(audio_data: AudioData) -> Optional[StructuralAnalysis]:
    """Synchronous structural analysis — runs in ThreadPoolExecutor."""
    try:
        return music_structure_analyzer.analyze(
            audio_source=None,
            audio_data=audio_data,
        )
    except Exception as e:
        logger.error(f"Structural analysis failed: {e}")
        return None


class AudioAnalyzer:
    """
    High-level async interface for audio analysis.

    Usage:
        result = await audio_analyzer.analyze_from_url(preview_url)
        result = await audio_analyzer.analyze_from_url(preview_url, include_structure=True)
    """

    async def analyze_from_url(
        self,
        audio_url: str,
        include_structure: bool = True,
        isrc: Optional[str] = None,
        spotify_id: Optional[str] = None,
    ) -> Optional[AudioAnalysisResult]:
        """
        Download audio from URL, extract features, and optionally analyze structure.

        Args:
            audio_url: Spotify preview URL (30s MP3)
            include_structure: Whether to run SSM + clustering
            isrc: Optional ISRC for Deezer BPM/loudness enrichment

        Returns:
            AudioAnalysisResult or None if download/analysis failed
        """
        if not audio_url:
            return None

        audio_data = await audio_extractor.extract_from_url(
            audio_url,
            isrc=isrc,
            spotify_id=spotify_id,
        )
        if not audio_data:
            return None

        structural_analysis = None
        if include_structure:
            loop = asyncio.get_event_loop()
            structural_analysis = await loop.run_in_executor(
                _executor, _run_structural_analysis, audio_data
            )

        return AudioAnalysisResult(
            audio_data=audio_data,
            structural_analysis=structural_analysis,
        )

    async def analyze_multiple(
        self,
        audio_urls: List[str],
        include_structure: bool = False,
    ) -> List[Optional[AudioAnalysisResult]]:
        """Analyze multiple audio files concurrently."""
        tasks = [self.analyze_from_url(url, include_structure) for url in audio_urls]
        return await asyncio.gather(*tasks, return_exceptions=False)

    def calculate_similarity(
        self,
        result1: AudioAnalysisResult,
        result2: AudioAnalysisResult,
        use_structure: bool = True,
    ) -> float:
        """
        Calculate similarity between two analysis results.
        Combines MFCC cosine similarity (50%) and structural similarity (50%).
        """
        if not result1 or not result2:
            return 0.0

        # MFCC cosine similarity
        mfcc_sim = 0.0
        d1, d2 = result1.audio_data, result2.audio_data
        if d1 is not None and d2 is not None:
            import numpy as np
            v1 = audio_extractor.to_feature_vector(d1)
            v2 = audio_extractor.to_feature_vector(d2)
            norm1, norm2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
            if norm1 > 0 and norm2 > 0:
                mfcc_sim = float(np.dot(v1, v2) / (norm1 * norm2))

        # Structural similarity
        struct_sim = 0.0
        if (
            use_structure
            and result1.structural_analysis
            and result2.structural_analysis
        ):
            struct_sim = music_structure_analyzer.compute_structural_similarity(
                result1.structural_analysis,
                result2.structural_analysis,
            )

        if use_structure and struct_sim > 0:
            return float(max(0.0, min(1.0, 0.5 * mfcc_sim + 0.5 * struct_sim)))
        return float(max(0.0, min(1.0, mfcc_sim)))


audio_analyzer = AudioAnalyzer()
