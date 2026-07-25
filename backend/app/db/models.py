from sqlalchemy import Column, String, DateTime, ForeignKey, ARRAY, Text, JSON
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
