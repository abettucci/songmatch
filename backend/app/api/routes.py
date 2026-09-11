"""
API routes for SongMatch.

All endpoints avoid deprecated Spotify APIs:
- Audio features endpoint uses librosa (not Spotify audio-features)
- Recommendations do not use Spotify recommendations endpoint

New endpoint added:
- GET /api/v1/auth/me — returns current user from JWT (fixes useAuth.tsx placeholder bug)
"""

import asyncio
import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict
from uuid import UUID
import logging

from app.db.database import get_db
from app.db.repository import (
    UserRepository,
    PlaylistRepository,
    RecommendationHistoryRepository,
    TrackAudioFeaturesRepository,
    ListeningHistoryRepository,
)
from app.core.security import create_access_token, require_auth, get_current_user_id
from app.core.config import get_settings
from app.services.spotify import SpotifyAPIError, spotify_client
from app.services.spotify_tokens import get_valid_access_token
from app.services.recommendations import recommendation_engine
from app.services.audio_analysis import audio_analyzer
from app.services.audio_features import audio_extractor
from app.services.visualization import structure_visualizer
from app.api.schemas import (
    UserCreate, UserLogin, AuthResponse, UserResponse, MessageResponse,
    SearchRequest, SearchResponse, TrackResponse,
    RecommendationRequest, RecommendationResponse,
    AudioFeaturesRequest, AudioFeaturesResponse, AudioFeature,
    PlaylistCreate, PlaylistResponse, PlaylistListResponse,
    HealthResponse,
    StructuralAnalysisRequest, StructuralAnalysisResponse, SectionResponse,
    VisualizationRequest, VisualizationResponse,
    SpotifyAuthUrlResponse, SpotifyTopTracksResponse,
    SpotifyPlaylistGenreRequest, SpotifyPlaylistGenreCreateRequest,
    SpotifyPlaylistGenrePreviewResponse, SpotifyPlaylistGenreCreateResponse,
    TrackWithPlayedAt, SpotifyRecentlyPlayedResponse,
    SpotifyListeningHistoryGenreGroup, SpotifyListeningHistoryDay,
    SpotifyListeningHistoryResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# ──────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        version="1.0.0",
        environment=settings.environment,
    )


# ──────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────

@router.post("/api/v1/auth/register", response_model=AuthResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    user_repo = UserRepository(db)

    existing_user = await user_repo.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = await user_repo.create(user_data.email, user_data.password)
    token = create_access_token({"sub": str(user.id)})

    return AuthResponse(
        user=UserResponse(
            id=user.id, email=user.email, created_at=user.created_at,
            spotify_connected=bool(user.spotify_access_token),
        ),
        token=token,
    )


@router.post("/api/v1/auth/login", response_model=AuthResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    user_repo = UserRepository(db)

    user = await user_repo.authenticate(credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": str(user.id)})

    return AuthResponse(
        user=UserResponse(
            id=user.id, email=user.email, created_at=user.created_at,
            spotify_connected=bool(user.spotify_access_token),
        ),
        token=token,
    )


@router.get("/api/v1/auth/me", response_model=UserResponse)
async def get_current_user(
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the authenticated user's profile.
    Fixes useAuth.tsx bug: previously used a placeholder instead of calling this endpoint.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(UUID(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return UserResponse(
        id=user.id, email=user.email, created_at=user.created_at,
        spotify_connected=bool(user.spotify_access_token),
    )


@router.post("/api/v1/auth/logout", response_model=MessageResponse)
async def logout():
    """Logout (client should discard the JWT)."""
    return MessageResponse(message="Logged out successfully")


# ──────────────────────────────────────────────────────
# Spotify OAuth (additive feature — does not replace email/password auth)
# ──────────────────────────────────────────────────────

def _build_spotify_state(user_id: str) -> str:
    """Build a CSRF-safe state: base64url(user_id:hmac_sha256(user_id, jwt_secret))."""
    sig = hmac.new(
        settings.jwt_secret_key.encode(),
        user_id.encode(),
        hashlib.sha256,
    ).hexdigest()
    raw = f"{user_id}:{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _verify_spotify_state(state: str) -> Optional[str]:
    """Verify state and return user_id if valid, else None."""
    try:
        raw = base64.urlsafe_b64decode(state.encode()).decode()
        user_id, sig = raw.rsplit(":", 1)
        expected = hmac.new(
            settings.jwt_secret_key.encode(),
            user_id.encode(),
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(sig, expected):
            return user_id
    except Exception:
        pass
    return None


def _build_playlist_genre_confirmation_token(user_id: str, playlist_id: str) -> str:
    """Issue a short-lived, user-bound proof that the playlist was previewed."""
    expires_at = int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp())
    payload = f"{user_id}:{playlist_id}:{expires_at}"
    signature = hmac.new(
        settings.jwt_secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def _is_valid_playlist_genre_confirmation_token(
    token: str, user_id: str, playlist_id: str
) -> bool:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        token_user_id, token_playlist_id, expires_at, signature = decoded.rsplit(":", 3)
        payload = f"{token_user_id}:{token_playlist_id}:{expires_at}"
        expected_signature = hmac.new(
            settings.jwt_secret_key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return (
            hmac.compare_digest(signature, expected_signature)
            and hmac.compare_digest(token_user_id, user_id)
            and hmac.compare_digest(token_playlist_id, playlist_id)
            and int(expires_at) >= int(datetime.now(timezone.utc).timestamp())
        )
    except (ValueError, UnicodeDecodeError):
        return False


@router.get("/api/v1/auth/spotify/login", response_model=SpotifyAuthUrlResponse)
async def spotify_login(user_id: str = Depends(require_auth)):
    """Return the Spotify authorization URL. Frontend should open it in the browser."""
    state = _build_spotify_state(user_id)
    auth_url = spotify_client.get_oauth_url(state)
    return SpotifyAuthUrlResponse(auth_url=auth_url)


@router.get("/api/v1/auth/spotify/callback")
async def spotify_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Spotify redirects here after user authorizes. Stores tokens and redirects to frontend."""
    # "/dashboard" doesn't exist as a route (App.tsx only defines "/" and "/auth");
    # useAuth.tsx reads ?spotify=connected from window.location.search regardless
    # of path, so redirecting to "/" (the actual dashboard route) works the same.
    frontend_url = settings.frontend_url

    if error or not code or not state:
        return RedirectResponse(url=f"{frontend_url}?spotify=error")

    user_id = _verify_spotify_state(state)
    if not user_id:
        return RedirectResponse(url=f"{frontend_url}?spotify=error")

    try:
        token_data = await spotify_client.exchange_code(code)
    except Exception:
        return RedirectResponse(url=f"{frontend_url}?spotify=error")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))

    user_repo = UserRepository(db)
    await user_repo.save_spotify_tokens(
        user_id=UUID(user_id),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        expires_at=expires_at,
    )

    return RedirectResponse(url=f"{frontend_url}?spotify=connected")


@router.delete("/api/v1/auth/spotify/disconnect", response_model=MessageResponse)
async def spotify_disconnect(
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Remove Spotify tokens from the user's account."""
    user_repo = UserRepository(db)
    await user_repo.clear_spotify_tokens(UUID(user_id))
    return MessageResponse(message="Spotify disconnected")


@router.get("/api/v1/auth/spotify/top-tracks", response_model=SpotifyTopTracksResponse)
async def spotify_top_tracks(
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's top tracks from Spotify (requires connected account)."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(UUID(user_id))

    if not user or not user.spotify_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spotify account not connected",
        )

    # Falls back to the (possibly stale) stored token if refresh fails, matching
    # this endpoint's previous behavior of trying anyway rather than hard-failing.
    access_token = await get_valid_access_token(user, db) or user.spotify_access_token

    tracks = await spotify_client.get_user_top_tracks(access_token, limit=20)
    return SpotifyTopTracksResponse(tracks=[TrackResponse(**t) for t in tracks])


async def _get_spotify_access_token_for_user(user_id: str, db: AsyncSession) -> str:
    """Resolve and refresh only the authenticated user's Spotify token."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(UUID(user_id))
    if not user or not user.spotify_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spotify account not connected",
        )

    access_token = await get_valid_access_token(user, db)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Spotify connection expired. Reconnect Spotify and try again.",
        )
    return access_token


@router.get("/api/v1/spotify/recently-played", response_model=SpotifyRecentlyPlayedResponse)
async def spotify_recently_played(
    limit: int = Query(20, ge=1, le=50),
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Live 'last played' snapshot from Spotify (always fresh, never DB-only).

    Also opportunistically upserts what it fetches into listening_history, so
    gaps between the daily sync job's runs get partially filled for free.
    """
    access_token = await _get_spotify_access_token_for_user(user_id, db)
    plays = await spotify_client.get_user_recently_played(access_token, limit=limit)

    if plays:
        genres_by_track = await spotify_client.genres_for_tracks(plays)
        for play in plays:
            play["genres"] = genres_by_track.get(play["spotify_id"], [])
        await ListeningHistoryRepository(db).upsert_many(UUID(user_id), plays)

    return SpotifyRecentlyPlayedResponse(tracks=[TrackWithPlayedAt(**p) for p in plays])


@router.get("/api/v1/spotify/listening-history", response_model=SpotifyListeningHistoryResponse)
async def spotify_listening_history(
    days: int = Query(7, ge=1, le=30),
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Persisted history (populated by the daily sync job + the live endpoint
    above), grouped by UTC calendar day and then by each track's primary genre
    — the first genre snapshotted for that track, or 'Sin género' if it has
    none. Each track lands in exactly one genre group, never duplicated."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await ListeningHistoryRepository(db).get_by_user_since(UUID(user_id), since)

    days_map: Dict[str, Dict[str, List[TrackWithPlayedAt]]] = {}
    for row in rows:
        day_key = row.played_at.astimezone(timezone.utc).date().isoformat()
        genre_name = row.genres[0] if row.genres else "Sin género"
        track = TrackWithPlayedAt(
            spotify_id=row.spotify_track_id,
            name=row.track_name,
            artist=row.artist,
            album=row.album,
            album_image=row.album_image,
            external_url=row.external_url,
            played_at=row.played_at,
        )
        days_map.setdefault(day_key, {}).setdefault(genre_name, []).append(track)

    response_days = [
        SpotifyListeningHistoryDay(
            date=day_key,
            genres=[
                SpotifyListeningHistoryGenreGroup(name=genre_name, tracks=tracks)
                for genre_name, tracks in genre_groups.items()
            ],
            total_tracks=sum(len(tracks) for tracks in genre_groups.values()),
        )
        for day_key, genre_groups in sorted(days_map.items(), reverse=True)
    ]
    return SpotifyListeningHistoryResponse(days=response_days)


def _spotify_error_to_http(error: SpotifyAPIError) -> HTTPException:
    if error.status_code == 404:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spotify playlist not found")
    if error.status_code in (401, 403):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Spotify denied access to this playlist. Reconnect Spotify and grant playlist permissions.",
        )
    if error.status_code == 429:
        return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Spotify is busy. Try again shortly.")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Spotify is temporarily unavailable")


@router.post(
    "/api/v1/spotify/playlist-genres/preview",
    response_model=SpotifyPlaylistGenrePreviewResponse,
)
async def preview_spotify_playlist_genres(
    request: SpotifyPlaylistGenreRequest,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Analyze a playlist before any Spotify write occurs."""
    access_token = await _get_spotify_access_token_for_user(user_id, db)
    try:
        analysis = await spotify_client.analyze_playlist_genres(access_token, request.playlist_id)
    except SpotifyAPIError as error:
        raise _spotify_error_to_http(error)

    return SpotifyPlaylistGenrePreviewResponse(
        playlist_id=request.playlist_id,
        playlist_name=analysis["playlist_name"],
        total_tracks=len(analysis["tracks"]),
        categorized_tracks=sum(
            1
            for track in analysis["tracks"]
            if any(
                analysis["genres_by_artist"].get(artist.get("id"))
                for artist in track.get("artists", [])
            )
        ),
        genres=analysis["genres"],
        confirmation_token=_build_playlist_genre_confirmation_token(user_id, request.playlist_id),
    )


@router.post(
    "/api/v1/spotify/playlist-genres/create",
    response_model=SpotifyPlaylistGenreCreateResponse,
)
async def create_genre_spotify_playlist(
    request: SpotifyPlaylistGenreCreateRequest,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Create a private playlist only after the client has explicitly confirmed it."""
    if not _is_valid_playlist_genre_confirmation_token(
        request.confirmation_token, user_id, request.playlist_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Playlist preview expired. Analyze the playlist again before creating it.",
        )
    access_token = await _get_spotify_access_token_for_user(user_id, db)
    try:
        analysis = await spotify_client.analyze_playlist_genres(access_token, request.playlist_id)
    except SpotifyAPIError as error:
        raise _spotify_error_to_http(error)

    requested_genre = request.genre.casefold()
    valid_genres = {genre["name"].casefold(): genre["name"] for genre in analysis["genres"]}
    genre_name = valid_genres.get(requested_genre)
    if not genre_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Genre is not available for this playlist")

    matching_uris = []
    for track in analysis["tracks"]:
        track_genres = {
            " ".join(genre.split()).casefold()
            for artist in track.get("artists", [])
            for genre in analysis["genres_by_artist"].get(artist.get("id"), [])
        }
        if requested_genre in track_genres and track.get("uri"):
            matching_uris.append(track["uri"])
    if not matching_uris:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No tracks match this genre anymore")

    playlist_name = f"{analysis['playlist_name']} — {genre_name}"[:100]
    try:
        created_playlist = await spotify_client.create_private_playlist(
            access_token,
            playlist_name,
            f"Created by SoundMatch from {analysis['playlist_name'][:60]} ({genre_name}).",
        )
        await spotify_client.add_playlist_tracks(access_token, created_playlist["id"], matching_uris)
    except SpotifyAPIError as error:
        raise _spotify_error_to_http(error)

    return SpotifyPlaylistGenreCreateResponse(
        playlist_id=created_playlist["id"],
        playlist_name=created_playlist.get("name", playlist_name),
        playlist_url=created_playlist.get("external_urls", {}).get("spotify", ""),
        genre=genre_name,
        track_count=len(matching_uris),
    )


# ──────────────────────────────────────────────────────
# Search
# ──────────────────────────────────────────────────────

@router.post("/api/v1/search", response_model=SearchResponse)
async def search_tracks(request: SearchRequest):
    """Search for tracks on Spotify."""
    tracks = await spotify_client.search_tracks(request.query, request.limit)
    return SearchResponse(tracks=[TrackResponse(**t) for t in tracks])


# ──────────────────────────────────────────────────────
# Recommendations
# ──────────────────────────────────────────────────────

@router.post("/api/v1/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest,
    user_id: Optional[str] = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get music recommendations based on seed tracks."""
    feature_cache = TrackAudioFeaturesRepository(db)
    result = await recommendation_engine.get_recommendations(
        seed_tracks=request.seed_tracks,
        algorithm=request.algorithm,
        limit=request.limit,
        filters=request.filters,
        feature_cache=feature_cache,
    )

    # Persist recommendation history for authenticated users
    if user_id:
        try:
            history_repo = RecommendationHistoryRepository(db)
            rec_ids = [r.get("spotify_id", "") for r in result.get("recommendations", [])]
            await history_repo.create(
                seed_tracks=request.seed_tracks,
                algorithm=request.algorithm,
                recommendations=rec_ids,
                user_id=UUID(user_id),
            )
        except Exception as e:
            logger.warning(f"Failed to save recommendation history: {e}")

    # Build TrackResponse objects, ignoring unknown extra fields with model_validate
    def to_track(d: dict) -> TrackResponse:
        return TrackResponse.model_validate({k: v for k, v in d.items() if k in TrackResponse.model_fields})

    recommendations = [to_track(r) for r in result.get("recommendations", [])]
    seed_tracks = [to_track(t) for t in result.get("seed_tracks", [])]

    return RecommendationResponse(
        recommendations=recommendations,
        method=result.get("method", "unknown"),
        seed_tracks=seed_tracks,
        algorithm_used=result.get("algorithm_used", request.algorithm),
        count=result.get("count", len(recommendations)),
        error=result.get("error"),
    )


# ──────────────────────────────────────────────────────
# Audio Features (librosa-based, not Spotify deprecated endpoint)
# ──────────────────────────────────────────────────────

@router.post("/api/v1/audio-features", response_model=AudioFeaturesResponse)
async def get_audio_features(request: AudioFeaturesRequest):
    """
    Extract audio features using librosa from preview URLs.
    Uses the 3-layer architecture: librosa (base) → Deezer (BPM) → Cyanite.ai (valence).
    """
    tasks = [audio_extractor.extract_from_url(url) for url in request.preview_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    features = []
    for url, result in zip(request.preview_urls, results):
        if not isinstance(result, Exception) and result is not None:
            features.append(AudioFeature(
                preview_url=url,
                tempo=result.tempo,
                energy=result.energy,
                valence=result.valence,
                arousal=result.arousal,
                danceability=result.danceability,
                acousticness=result.acousticness,
                instrumentalness=result.instrumentalness,
                speechiness=result.speechiness,
                liveness=result.liveness,
                loudness=result.loudness,
                duration=result.duration,
                key=result.key,
                time_signature=result.time_signature,
                source=result.feature_source,
                genre_tags=result.genre_tags,
                subgenre_tags=result.subgenre_tags,
                mood_tags=result.mood_tags,
                movement_tags=result.movement_tags,
                character_tags=result.character_tags,
                instrument_tags=result.instrument_tags,
                voice_tags=result.voice_tags,
            ))

    return AudioFeaturesResponse(audio_features=features)


# ──────────────────────────────────────────────────────
# Structural Analysis
# ──────────────────────────────────────────────────────

@router.post("/api/v1/analyze-structure", response_model=StructuralAnalysisResponse)
async def analyze_structure(request: StructuralAnalysisRequest):
    """
    Perform structural analysis on an audio track (10-30s).

    Implements Martínez 2023 methodology:
    - Self-Similarity Matrix from mel spectrogram + chromagram
    - Foote novelty detection with checkerboard kernel
    - Hierarchical Ward clustering for section labeling (A, B, C...)
    """
    result = await audio_analyzer.analyze_from_url(
        request.preview_url,
        include_structure=True,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to analyze audio. Verify the URL is accessible.",
        )

    if not result.structural_analysis:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Structural analysis failed.",
        )

    sa = result.structural_analysis
    ad = result.audio_data

    sections = [
        SectionResponse(
            start_time=s.start_time,
            end_time=s.end_time,
            duration=s.duration,
            cluster_id=s.cluster_id,
            label=s.label,
            loudness=s.loudness,
        )
        for s in sa.sections
    ]

    return StructuralAnalysisResponse(
        duration=sa.duration,
        tempo=ad.tempo if ad else None,
        energy=ad.energy if ad else None,
        valence=ad.valence if ad else None,
        n_sections=len(sections),
        n_clusters=sa.n_clusters,
        silhouette_score=sa.silhouette_score,
        structure_pattern=result.structure_pattern,
        sections=sections,
    )


@router.post("/api/v1/visualize-structure", response_model=VisualizationResponse)
async def visualize_structure(request: VisualizationRequest):
    """
    Generate base64-encoded PNG visualizations for structural analysis.

    Returns: SSM heatmap, novelty curve, structure diagram, combined view.
    Use as: <img src="data:image/png;base64,{image}" />
    """
    result = await audio_analyzer.analyze_from_url(
        request.preview_url,
        include_structure=True,
    )

    if not result or not result.structural_analysis:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to analyze audio for visualization.",
        )

    frame_times = result.audio_data.frame_times if result.audio_data else None

    visualizations = structure_visualizer.generate_all_visualizations(
        result.structural_analysis,
        frame_times,
    )

    return VisualizationResponse(
        combined=visualizations.get("combined") if request.include_combined else None,
        ssm=visualizations.get("ssm") if request.include_ssm else None,
        novelty=visualizations.get("novelty") if request.include_novelty else None,
        structure=visualizations.get("structure") if request.include_structure else None,
        structure_pattern=result.structure_pattern,
        n_sections=len(result.structural_analysis.sections),
    )


# ──────────────────────────────────────────────────────
# Playlists
# ──────────────────────────────────────────────────────

@router.post("/api/v1/playlists", response_model=PlaylistResponse)
async def create_playlist(
    playlist_data: PlaylistCreate,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    playlist_repo = PlaylistRepository(db)
    playlist = await playlist_repo.create(
        user_id=UUID(user_id),
        name=playlist_data.name,
        tracks=playlist_data.tracks,
    )
    return PlaylistResponse(
        id=playlist.id,
        user_id=playlist.user_id,
        name=playlist.name,
        tracks=playlist.tracks or [],
        created_at=playlist.created_at,
    )


@router.get("/api/v1/playlists", response_model=PlaylistListResponse)
async def get_playlists(
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    playlist_repo = PlaylistRepository(db)
    playlists = await playlist_repo.get_by_user(UUID(user_id))
    return PlaylistListResponse(
        playlists=[
            PlaylistResponse(
                id=p.id,
                user_id=p.user_id,
                name=p.name,
                tracks=p.tracks or [],
                created_at=p.created_at,
            )
            for p in playlists
        ]
    )


@router.get("/api/v1/playlists/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: UUID,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    playlist_repo = PlaylistRepository(db)
    playlist = await playlist_repo.get_by_id(playlist_id, UUID(user_id))

    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    return PlaylistResponse(
        id=playlist.id,
        user_id=playlist.user_id,
        name=playlist.name,
        tracks=playlist.tracks or [],
        created_at=playlist.created_at,
    )


@router.delete("/api/v1/playlists/{playlist_id}", response_model=MessageResponse)
async def delete_playlist(
    playlist_id: UUID,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    playlist_repo = PlaylistRepository(db)
    deleted = await playlist_repo.delete(playlist_id, UUID(user_id))

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    return MessageResponse(message="Playlist deleted successfully")
