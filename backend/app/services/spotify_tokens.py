"""Shared Spotify user-token resolution, used by both HTTP routes and the
standalone sync job. Framework-agnostic: never raises HTTPException, so the
job (which loops over every user) can just skip a user on failure instead of
aborting the whole run.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repository import UserRepository
from app.services.spotify import spotify_client

logger = logging.getLogger(__name__)


async def get_valid_access_token(user: User, db: AsyncSession) -> Optional[str]:
    """Return a usable Spotify access token for this user, refreshing and
    persisting it first if it's expired or about to expire. Returns None if
    the user has no Spotify connection or the refresh fails."""
    if not user.spotify_access_token:
        return None

    access_token = user.spotify_access_token
    expires_at = user.spotify_token_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at and expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
        try:
            token_data = await spotify_client.refresh_user_token(user.spotify_refresh_token)
        except Exception:
            logger.warning("Spotify token refresh failed for user %s", user.id)
            return None

        user_repo = UserRepository(db)
        await user_repo.save_spotify_tokens(
            user_id=user.id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", user.spotify_refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600)),
        )
        access_token = token_data["access_token"]

    return access_token
