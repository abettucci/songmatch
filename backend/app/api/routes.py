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
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
import logging

from app.db.database import get_db
from app.db.repository import (
    UserRepository,
    PlaylistRepository,
    RecommendationHistoryRepository,
    TrackAudioFeaturesRepository,
)
from app.core.security import create_access_token, require_auth, get_current_user_id
from app.core.config import get_settings
from app.services.spotify import spotify_client
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
    frontend_url = f"{settings.frontend_url}/dashboard"

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

    access_token = user.spotify_access_token

    # Refresh token if expired (or about to expire)
    if user.spotify_token_expires_at:
        expires_at = user.spotify_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
            try:
                token_data = await spotify_client.refresh_user_token(user.spotify_refresh_token)
                new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))
                await user_repo.save_spotify_tokens(
                    user_id=UUID(user_id),
                    access_token=token_data["access_token"],
                    refresh_token=token_data.get("refresh_token", user.spotify_refresh_token),
                    expires_at=new_expires_at,
                )
                access_token = token_data["access_token"]
            except Exception as e:
                logger.warning(f"Failed to refresh Spotify token for user {user_id}: {e}")

    tracks = await spotify_client.get_user_top_tracks(access_token, limit=20)
    return SpotifyTopTracksResponse(tracks=[TrackResponse(**t) for t in tracks])


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
