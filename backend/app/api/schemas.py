"""
Pydantic v2 schemas for the SongMatch API.

Key fixes vs previous version:
- TrackResponse uses spotify_id (not id) — matches frontend expectations
- TrackResponse uses album_image (not image_url) — matches spotify._format_track()
- RecommendationRequest uses min_length/max_length (Pydantic v2 syntax, not min_items)
- UserResponse and PlaylistResponse use model_config = ConfigDict (Pydantic v2)
- AudioFeaturesRequest uses preview_urls (librosa-based, not Spotify deprecated endpoint)
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID


# ──────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime
    spotify_connected: bool = False


class AuthResponse(BaseModel):
    user: UserResponse
    token: str


# ──────────────────────────────────────────────────────
# Generic
# ──────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    environment: str


# ──────────────────────────────────────────────────────
# Tracks
# ──────────────────────────────────────────────────────

class SectionResponse(BaseModel):
    start_time: float
    end_time: float
    duration: float
    cluster_id: int
    label: str
    loudness: Optional[float] = None


class TrackResponse(BaseModel):
    """
    Represents a Spotify track.
    Field names match what spotify._format_track() returns:
      - spotify_id  (NOT id — frontend uses .spotify_id)
      - album_image (NOT image_url)
    """
    spotify_id: str
    name: str
    artist: str
    artist_id: Optional[str] = None
    artists: Optional[List[Dict[str, str]]] = None
    album: Optional[str] = None
    album_id: Optional[str] = None
    album_image: Optional[str] = None
    preview_url: Optional[str] = None
    duration_ms: Optional[int] = None
    popularity: Optional[int] = None
    external_url: Optional[str] = None
    uri: Optional[str] = None
    isrc: Optional[str] = None
    # Recommendation metadata
    match_score: Optional[float] = None
    similarity_score: Optional[float] = None
    source: Optional[str] = None
    audio_features: Optional[Dict[str, Any]] = None
    structure_pattern: Optional[str] = None
    n_sections: Optional[int] = None
    sections: Optional[List[SectionResponse]] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=20, ge=1, le=50)


class SearchResponse(BaseModel):
    tracks: List[TrackResponse]


# ──────────────────────────────────────────────────────
# Recommendations
# ──────────────────────────────────────────────────────

class RecommendationRequest(BaseModel):
    seed_tracks: List[str] = Field(..., min_length=1, max_length=5)
    algorithm: Literal["lastfm", "custom", "audio", "structural", "clap"] = "lastfm"
    limit: int = Field(default=20, ge=1, le=50)
    filters: Optional[Dict[str, Any]] = None


class RecommendationResponse(BaseModel):
    recommendations: List[TrackResponse]
    method: str
    seed_tracks: List[TrackResponse]
    algorithm_used: str
    count: int
    error: Optional[str] = None


# ──────────────────────────────────────────────────────
# Audio Features (via librosa — NOT Spotify deprecated endpoint)
# ──────────────────────────────────────────────────────

class AudioFeaturesRequest(BaseModel):
    preview_urls: List[str] = Field(..., min_length=1, max_length=20)


class AudioFeature(BaseModel):
    preview_url: str
    tempo: Optional[float] = None
    energy: Optional[float] = None
    valence: Optional[float] = None
    arousal: Optional[float] = None
    danceability: Optional[float] = None
    acousticness: Optional[float] = None
    instrumentalness: Optional[float] = None
    speechiness: Optional[float] = None
    liveness: Optional[float] = None
    loudness: Optional[float] = None
    duration: Optional[float] = None
    key: Optional[str] = None
    time_signature: Optional[str] = None
    source: Optional[str] = None
    genre_tags: Optional[List[str]] = None
    subgenre_tags: Optional[List[str]] = None
    mood_tags: Optional[List[str]] = None
    movement_tags: Optional[List[str]] = None
    character_tags: Optional[List[str]] = None
    instrument_tags: Optional[List[str]] = None
    voice_tags: Optional[List[str]] = None


class AudioFeaturesResponse(BaseModel):
    audio_features: List[AudioFeature]


# ──────────────────────────────────────────────────────
# Structural Analysis
# ──────────────────────────────────────────────────────

class StructuralAnalysisRequest(BaseModel):
    preview_url: str = Field(..., description="Spotify preview URL (30s MP3)")


class StructuralAnalysisResponse(BaseModel):
    duration: float
    tempo: Optional[float] = None
    energy: Optional[float] = None
    valence: Optional[float] = None
    n_sections: int
    n_clusters: int
    silhouette_score: float
    structure_pattern: str
    sections: List[SectionResponse]


class VisualizationRequest(BaseModel):
    preview_url: str = Field(..., description="Spotify preview URL")
    include_combined: bool = True
    include_ssm: bool = True
    include_novelty: bool = True
    include_structure: bool = True


class VisualizationResponse(BaseModel):
    combined: Optional[str] = None
    ssm: Optional[str] = None
    novelty: Optional[str] = None
    structure: Optional[str] = None
    structure_pattern: str
    n_sections: int


# ──────────────────────────────────────────────────────
# Playlists
# ──────────────────────────────────────────────────────

class PlaylistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    tracks: List[str] = Field(default=[])


class PlaylistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    tracks: List[str]
    created_at: datetime


class PlaylistListResponse(BaseModel):
    playlists: List[PlaylistResponse]


# ──────────────────────────────────────────────────────
# Spotify OAuth
# ──────────────────────────────────────────────────────

class SpotifyAuthUrlResponse(BaseModel):
    auth_url: str


class SpotifyTopTracksResponse(BaseModel):
    tracks: List[TrackResponse]


# ──────────────────────────────────────────────────────
# Spotify recently played / listening history
# ──────────────────────────────────────────────────────

class TrackWithPlayedAt(TrackResponse):
    played_at: datetime


class SpotifyRecentlyPlayedResponse(BaseModel):
    tracks: List[TrackWithPlayedAt]


class TrackWithAddedAt(TrackResponse):
    added_at: datetime


class SpotifyLikedTracksGenreGroup(BaseModel):
    name: str
    tracks: List[TrackWithAddedAt]


class SpotifyLikedTracksResponse(BaseModel):
    tracks: List[TrackWithAddedAt]
    genres: List[SpotifyLikedTracksGenreGroup]


class SpotifyListeningHistoryGenreGroup(BaseModel):
    name: str
    tracks: List[TrackWithPlayedAt]


class SpotifyListeningHistoryDay(BaseModel):
    date: str  # ISO calendar date (UTC), e.g. "2026-09-11"
    genres: List[SpotifyListeningHistoryGenreGroup]
    total_tracks: int = Field(ge=0)


class SpotifyListeningHistoryResponse(BaseModel):
    days: List[SpotifyListeningHistoryDay]


# ──────────────────────────────────────────────────────
# Spotify playlist genre organizer
# ──────────────────────────────────────────────────────

SPOTIFY_PLAYLIST_ID_PATTERN = r"^[A-Za-z0-9]{22}$"


class SpotifyPlaylistGenreRequest(BaseModel):
    """A Spotify playlist identifier, never an arbitrary URL."""

    playlist_id: str = Field(
        ...,
        min_length=22,
        max_length=22,
        pattern=SPOTIFY_PLAYLIST_ID_PATTERN,
    )


class SpotifyPlaylistGenreCreateRequest(SpotifyPlaylistGenreRequest):
    genre: str = Field(..., min_length=1, max_length=100)
    confirmation_token: str = Field(..., min_length=32, max_length=512)

    @field_validator("genre")
    @classmethod
    def normalize_genre(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("genre must not be blank")
        return normalized


class SpotifyGenreSummary(BaseModel):
    name: str
    track_count: int = Field(ge=1)


class SpotifyPlaylistGenreTrackGroup(SpotifyGenreSummary):
    """Tracks from the source playlist that belong to this genre.

    A track can appear in more than one group because Spotify genres are
    artist-level metadata rather than a single exclusive track category.
    """

    tracks: List[TrackResponse]


class SpotifyPlaylistGenrePreviewResponse(BaseModel):
    playlist_id: str
    playlist_name: str
    total_tracks: int = Field(ge=0)
    categorized_tracks: int = Field(ge=0)
    tracks: List[TrackResponse]
    genres: List[SpotifyGenreSummary]
    genre_tracks: List[SpotifyPlaylistGenreTrackGroup]
    confirmation_token: str


class SpotifyPlaylistGenreCreateResponse(BaseModel):
    playlist_id: str
    playlist_name: str
    playlist_url: str
    genre: str
    track_count: int = Field(ge=1)


# ──────────────────────────────────────────────────────
# Concert companions
# ──────────────────────────────────────────────────────

CompanionStatus = Literal["active", "withdrawn"]
CompanionSwipeAction = Literal["pass", "interested"]
ConcertStatus = Literal["scheduled", "cancelled", "completed"]
ReportReason = Literal["safety", "harassment", "spam", "other"]


class CompanionProfileUpsert(BaseModel):
    display_name: str = Field(min_length=2, max_length=50)
    bio: str = Field(default="", max_length=280)
    city: str = Field(min_length=2, max_length=80)
    public_interests: List[str] = Field(default_factory=list, max_length=5)
    visible: bool = True
    music_affinity_consent: bool = False
    adult_confirmed: bool

    @field_validator("display_name", "bio", "city")
    @classmethod
    def trim_profile_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("public_interests")
    @classmethod
    def validate_interests(cls, values: List[str]) -> List[str]:
        normalized = []
        seen = set()
        for value in values:
            clean = " ".join(value.split())
            key = clean.casefold()
            if not clean or len(clean) > 80 or key in seen:
                continue
            seen.add(key)
            normalized.append(clean)
        if len(normalized) > 5:
            raise ValueError("public_interests allows up to 5 unique items")
        return normalized


class CompanionProfileResponse(BaseModel):
    user_id: UUID
    display_name: str
    bio: str
    city: str
    public_interests: List[str]
    visible: bool
    music_affinity_consent: bool
    adult_confirmed: bool


class ConcertCreate(BaseModel):
    artist: str = Field(min_length=1, max_length=160)
    venue: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=2, max_length=80)
    starts_at: datetime
    status: ConcertStatus = "scheduled"

    @field_validator("artist", "venue", "city")
    @classmethod
    def trim_concert_text(cls, value: str) -> str:
        return " ".join(value.split())


class ConcertResponse(BaseModel):
    id: UUID
    artist: str
    venue: str
    city: str
    starts_at: datetime
    status: ConcertStatus
    attending: bool = False


class AttendanceIntentRequest(BaseModel):
    status: CompanionStatus


class CompanionCandidateResponse(BaseModel):
    user_id: UUID
    display_name: str
    bio: str
    city: str
    public_interests: List[str]
    affinity_score: int = Field(ge=0, le=100)
    affinity_level: Literal["alto", "medio", "bajo"]
    affinity_reasons: List[str] = Field(max_length=3)


class CompanionCandidatesResponse(BaseModel):
    concert: ConcertResponse
    candidates: List[CompanionCandidateResponse]


class CompanionSwipeRequest(BaseModel):
    target_user_id: UUID
    action: CompanionSwipeAction


class CompanionSwipeResponse(BaseModel):
    matched: bool
    match_id: Optional[UUID] = None


class CompanionMatchResponse(BaseModel):
    id: UUID
    concert: ConcertResponse
    companion: CompanionCandidateResponse
    created_at: datetime


class CompanionMatchesResponse(BaseModel):
    matches: List[CompanionMatchResponse]


class UserBlockRequest(BaseModel):
    user_id: UUID


class UserReportRequest(BaseModel):
    user_id: UUID
    reason: ReportReason
    note: str = Field(default="", max_length=500)
