from sqlalchemy import Column, String, DateTime, ForeignKey, ARRAY, Text, JSON, Boolean, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func
import uuid
from typing import Optional


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Spotify OAuth (optional — null if user hasn't connected Spotify)
    spotify_access_token = Column(Text, nullable=True)
    spotify_refresh_token = Column(Text, nullable=True)
    spotify_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    playlists = relationship("Playlist", back_populates="user", cascade="all, delete-orphan")
    recommendation_history = relationship("RecommendationHistory", back_populates="user", cascade="all, delete-orphan")


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    tracks = Column(ARRAY(Text), default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="playlists")


class RecommendationHistory(Base):
    __tablename__ = "recommendation_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    seed_tracks = Column(ARRAY(Text), default=list)
    algorithm = Column(String(50))
    recommendations = Column(JSON, default=list)  # JSONB in PostgreSQL
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="recommendation_history")


class TrackAudioFeatures(Base):
    __tablename__ = "track_audio_features"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spotify_id = Column(String(64), unique=True, nullable=False, index=True)
    isrc = Column(String(32), nullable=True, index=True)
    provider = Column(String(50), nullable=False, default="librosa")
    status = Column(String(50), nullable=False, default="finished")
    features = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ListeningHistory(Base):
    """One row per Spotify play. Table is partitioned by HASH(user_id) — see
    infrastructure/schema.sql. No relationship() to User: reads always go
    through ListeningHistoryRepository, scoped by user_id, never via a lazy join.
    """

    __tablename__ = "listening_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    spotify_track_id = Column(String(64), nullable=False)
    track_name = Column(String(500), nullable=False)
    artist = Column(String(500), nullable=False)
    album = Column(String(500), nullable=True)
    album_image = Column(Text, nullable=True)
    external_url = Column(Text, nullable=True)
    genres = Column(ARRAY(Text), default=list)
    played_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    display_name = Column(String(50), nullable=False)
    bio = Column(String(280), nullable=False, default="")
    city = Column(String(80), nullable=False)
    public_interests = Column(ARRAY(String(80)), nullable=False, default=list)
    visible = Column(Boolean, nullable=False, default=True)
    music_affinity_consent = Column(Boolean, nullable=False, default=False)
    adult_confirmed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Concert(Base):
    __tablename__ = "concerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artist = Column(String(160), nullable=False)
    venue = Column(String(160), nullable=False)
    city = Column(String(80), nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, default="scheduled")
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('scheduled', 'cancelled', 'completed')", name="ck_concerts_status"),
        Index("idx_concerts_starts_at", "starts_at"),
    )


class ConcertAttendanceIntent(Base):
    __tablename__ = "concert_attendance_intents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    concert_id = Column(UUID(as_uuid=True), ForeignKey("concerts.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "concert_id", name="uq_concert_attendance_user_concert"),
        CheckConstraint("status IN ('active', 'withdrawn')", name="ck_concert_attendance_status"),
        Index("idx_concert_attendance_active", "concert_id", "status"),
    )


class CompanionSwipe(Base):
    __tablename__ = "companion_swipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    concert_id = Column(UUID(as_uuid=True), ForeignKey("concerts.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("actor_user_id", "target_user_id", "concert_id", name="uq_companion_swipe_direction"),
        CheckConstraint("actor_user_id <> target_user_id", name="ck_companion_swipe_not_self"),
        CheckConstraint("action IN ('pass', 'interested')", name="ck_companion_swipe_action"),
    )


class CompanionMatch(Base):
    __tablename__ = "companion_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concert_id = Column(UUID(as_uuid=True), ForeignKey("concerts.id", ondelete="CASCADE"), nullable=False)
    user_low_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user_high_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("concert_id", "user_low_id", "user_high_id", name="uq_companion_match_pair"),
        CheckConstraint("user_low_id < user_high_id", name="ck_companion_match_order"),
    )


class UserBlock(Base):
    __tablename__ = "user_blocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blocker_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    blocked_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_user_block_direction"),
        CheckConstraint("blocker_user_id <> blocked_user_id", name="ck_user_block_not_self"),
    )


class UserReport(Base):
    __tablename__ = "user_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reported_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason = Column(String(40), nullable=False)
    note = Column(String(500), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("reporter_user_id <> reported_user_id", name="ck_user_report_not_self"),
        Index("idx_user_reports_reported", "reported_user_id", "created_at"),
    )
