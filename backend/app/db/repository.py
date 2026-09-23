from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging

from app.db.models import (
    User, Playlist, RecommendationHistory, TrackAudioFeatures, ListeningHistory,
    UserProfile, Concert, ConcertAttendanceIntent, CompanionSwipe, CompanionMatch,
    UserBlock, UserReport,
)
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

    async def list_with_spotify_connected(self) -> List[User]:
        result = await self.session.execute(
            select(User).where(User.spotify_access_token.isnot(None))
        )
        return list(result.scalars().all())


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


class ListeningHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_many(self, user_id: UUID, plays: List[dict]) -> None:
        """Bulk-insert plays, skipping rows that already exist for this
        (user_id, spotify_track_id, played_at) — makes re-running the sync
        job over an overlapping window idempotent instead of duplicating rows."""
        if not plays:
            return

        rows = [
            {
                "user_id": user_id,
                "spotify_track_id": play["spotify_id"],
                "track_name": play["name"],
                "artist": play["artist"],
                "album": play.get("album"),
                "album_image": play.get("album_image"),
                "external_url": play.get("external_url"),
                "genres": play.get("genres", []),
                "played_at": play["played_at"],
            }
            for play in plays
        ]

        stmt = pg_insert(ListeningHistory).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["user_id", "spotify_track_id", "played_at"]
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_by_user_since(self, user_id: UUID, since: datetime) -> List[ListeningHistory]:
        result = await self.session.execute(
            select(ListeningHistory)
            .where(ListeningHistory.user_id == user_id, ListeningHistory.played_at >= since)
            .order_by(ListeningHistory.played_at.desc())
        )
        return list(result.scalars().all())


class CompanionRepository:
    """All social reads are scoped to the acting user before reaching routes."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_profile(self, user_id: UUID) -> Optional[UserProfile]:
        return (await self.session.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()

    async def upsert_profile(self, user_id: UUID, **values) -> UserProfile:
        profile = await self.get_profile(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id, **values)
            self.session.add(profile)
        else:
            for key, value in values.items():
                setattr(profile, key, value)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def create_concert(self, user_id: UUID, **values) -> Concert:
        concert = Concert(created_by_user_id=user_id, **values)
        self.session.add(concert)
        await self.session.flush()
        await self.session.refresh(concert)
        return concert

    async def get_concert(self, concert_id: UUID) -> Optional[Concert]:
        return (await self.session.execute(select(Concert).where(Concert.id == concert_id))).scalar_one_or_none()

    async def list_concerts(self, user_id: UUID) -> list[tuple[Concert, bool]]:
        result = await self.session.execute(
            select(Concert, ConcertAttendanceIntent.status)
            .outerjoin(ConcertAttendanceIntent, and_(ConcertAttendanceIntent.concert_id == Concert.id, ConcertAttendanceIntent.user_id == user_id))
            .order_by(Concert.starts_at.asc())
        )
        return [(concert, status == "active") for concert, status in result.all()]

    async def set_attendance(self, user_id: UUID, concert_id: UUID, status: str) -> ConcertAttendanceIntent:
        intent = (await self.session.execute(select(ConcertAttendanceIntent).where(
            ConcertAttendanceIntent.user_id == user_id, ConcertAttendanceIntent.concert_id == concert_id,
        ))).scalar_one_or_none()
        if intent is None:
            intent = ConcertAttendanceIntent(user_id=user_id, concert_id=concert_id, status=status)
            self.session.add(intent)
        else:
            intent.status = status
        await self.session.flush()
        await self.session.refresh(intent)
        return intent

    async def is_active_attendee(self, user_id: UUID, concert_id: UUID) -> bool:
        result = await self.session.execute(select(ConcertAttendanceIntent.id).where(
            ConcertAttendanceIntent.user_id == user_id,
            ConcertAttendanceIntent.concert_id == concert_id,
            ConcertAttendanceIntent.status == "active",
        ))
        return result.scalar_one_or_none() is not None

    async def active_candidate_profiles(self, user_id: UUID, concert_id: UUID) -> list[UserProfile]:
        blocked_by_me = select(UserBlock.id).where(UserBlock.blocker_user_id == user_id, UserBlock.blocked_user_id == UserProfile.user_id).exists()
        blocked_me = select(UserBlock.id).where(UserBlock.blocker_user_id == UserProfile.user_id, UserBlock.blocked_user_id == user_id).exists()
        already_seen = select(CompanionSwipe.id).where(
            CompanionSwipe.actor_user_id == user_id,
            CompanionSwipe.target_user_id == UserProfile.user_id,
            CompanionSwipe.concert_id == concert_id,
        ).exists()
        result = await self.session.execute(
            select(UserProfile)
            .join(ConcertAttendanceIntent, ConcertAttendanceIntent.user_id == UserProfile.user_id)
            .where(
                ConcertAttendanceIntent.concert_id == concert_id,
                ConcertAttendanceIntent.status == "active",
                UserProfile.user_id != user_id,
                UserProfile.visible.is_(True),
                UserProfile.adult_confirmed.is_(True),
                UserProfile.music_affinity_consent.is_(True),
                ~blocked_by_me, ~blocked_me, ~already_seen,
            )
        )
        return list(result.scalars().all())

    async def get_history_genres(self, user_id: UUID, since: datetime) -> list[tuple[str, datetime]]:
        rows = await self.session.execute(select(ListeningHistory.genres, ListeningHistory.played_at).where(
            ListeningHistory.user_id == user_id, ListeningHistory.played_at >= since,
        ))
        return [(genre, played_at) for genres, played_at in rows.all() for genre in (genres or [])]

    async def swipe_and_match(self, user_id: UUID, target_user_id: UUID, concert_id: UUID, action: str) -> Optional[CompanionMatch]:
        swipe = (await self.session.execute(select(CompanionSwipe).where(
            CompanionSwipe.actor_user_id == user_id, CompanionSwipe.target_user_id == target_user_id,
            CompanionSwipe.concert_id == concert_id,
        ))).scalar_one_or_none()
        if swipe is None:
            swipe = CompanionSwipe(actor_user_id=user_id, target_user_id=target_user_id, concert_id=concert_id, action=action)
            self.session.add(swipe)
        else:
            swipe.action = action
        await self.session.flush()
        if action != "interested":
            return None
        reciprocal = (await self.session.execute(select(CompanionSwipe.id).where(
            CompanionSwipe.actor_user_id == target_user_id, CompanionSwipe.target_user_id == user_id,
            CompanionSwipe.concert_id == concert_id, CompanionSwipe.action == "interested",
        ))).scalar_one_or_none()
        if reciprocal is None:
            return None
        low_id, high_id = sorted((user_id, target_user_id), key=str)
        match = (await self.session.execute(select(CompanionMatch).where(
            CompanionMatch.concert_id == concert_id, CompanionMatch.user_low_id == low_id, CompanionMatch.user_high_id == high_id,
        ))).scalar_one_or_none()
        if match is None:
            match = CompanionMatch(concert_id=concert_id, user_low_id=low_id, user_high_id=high_id)
            self.session.add(match)
            await self.session.flush()
        return match

    async def list_matches(self, user_id: UUID) -> list[tuple[CompanionMatch, Concert, UserProfile]]:
        result = await self.session.execute(
            select(CompanionMatch, Concert, UserProfile)
            .join(Concert, Concert.id == CompanionMatch.concert_id)
            .join(UserProfile, or_(
                and_(CompanionMatch.user_low_id == user_id, UserProfile.user_id == CompanionMatch.user_high_id),
                and_(CompanionMatch.user_high_id == user_id, UserProfile.user_id == CompanionMatch.user_low_id),
            ))
            .where(or_(CompanionMatch.user_low_id == user_id, CompanionMatch.user_high_id == user_id))
            .order_by(CompanionMatch.created_at.desc())
        )
        return list(result.all())

    async def block(self, user_id: UUID, target_user_id: UUID) -> None:
        existing = (await self.session.execute(select(UserBlock.id).where(
            UserBlock.blocker_user_id == user_id, UserBlock.blocked_user_id == target_user_id,
        ))).scalar_one_or_none()
        if existing is None:
            self.session.add(UserBlock(blocker_user_id=user_id, blocked_user_id=target_user_id))
            await self.session.flush()

    async def report(self, user_id: UUID, target_user_id: UUID, reason: str, note: str) -> None:
        self.session.add(UserReport(reporter_user_id=user_id, reported_user_id=target_user_id, reason=reason, note=note))
        await self.session.flush()
