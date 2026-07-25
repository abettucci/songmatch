from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging

from app.db.models import User, Playlist, RecommendationHistory, TrackAudioFeatures
from app.core.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, email: str, password: str) -> User:
        password_hash = get_password_hash(password)
        user = User(email=email, password_hash=password_hash)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
    
    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def authenticate(self, email: str, password: str) -> Optional[User]:
        user = await self.get_by_email(email)
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def save_spotify_tokens(
        self,
        user_id: UUID,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
    ) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        user.spotify_access_token = access_token
        user.spotify_refresh_token = refresh_token
        user.spotify_token_expires_at = expires_at
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def clear_spotify_tokens(self, user_id: UUID) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        user.spotify_access_token = None
        user.spotify_refresh_token = None
        user.spotify_token_expires_at = None
        await self.session.flush()
        await self.session.refresh(user)
        return user


class PlaylistRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, user_id: UUID, name: str, tracks: List[str]) -> Playlist:
        playlist = Playlist(user_id=user_id, name=name, tracks=tracks)
        self.session.add(playlist)
        await self.session.flush()
        await self.session.refresh(playlist)
        return playlist
    
    async def get_by_user(self, user_id: UUID) -> List[Playlist]:
        result = await self.session.execute(
            select(Playlist)
            .where(Playlist.user_id == user_id)
            .order_by(Playlist.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_by_id(self, playlist_id: UUID, user_id: UUID) -> Optional[Playlist]:
        result = await self.session.execute(
            select(Playlist)
            .where(Playlist.id == playlist_id, Playlist.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def delete(self, playlist_id: UUID, user_id: UUID) -> bool:
        playlist = await self.get_by_id(playlist_id, user_id)
        if playlist:
            await self.session.delete(playlist)
            return True
        return False


class RecommendationHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self, 
        seed_tracks: List[str], 
        algorithm: str, 
        recommendations: List[str],
        user_id: Optional[UUID] = None
    ) -> RecommendationHistory:
        history = RecommendationHistory(
            user_id=user_id,
            seed_tracks=seed_tracks,
            algorithm=algorithm,
            recommendations=recommendations
        )
        self.session.add(history)
        await self.session.flush()
        return history


class TrackAudioFeaturesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_spotify_id(self, spotify_id: str) -> Optional[TrackAudioFeatures]:
        if not spotify_id:
            return None

        result = await self.session.execute(
            select(TrackAudioFeatures).where(TrackAudioFeatures.spotify_id == spotify_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        spotify_id: str,
        features: dict,
        provider: str = "librosa",
        status: str = "finished",
        isrc: Optional[str] = None,
    ) -> Optional[TrackAudioFeatures]:
        if not spotify_id:
            return None

        existing = await self.get_by_spotify_id(spotify_id)
        if existing:
            existing.features = features
            existing.provider = provider
            existing.status = status
            existing.isrc = isrc or existing.isrc
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        row = TrackAudioFeatures(
            spotify_id=spotify_id,
            isrc=isrc,
            provider=provider,
            status=status,
            features=features,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row
