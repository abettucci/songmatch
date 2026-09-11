"""Daily cron job: pull each connected user's Spotify "recently played" tracks
and persist them into listening_history.

Runs standalone (not as an HTTP endpoint), triggered by a scheduled Railway
service with its own Cron Schedule pointing at:

    python -m app.jobs.sync_recently_played

Not exposing this as an HTTP route avoids having to protect an extra
unauthenticated network surface just to trigger a background sync.
"""

import asyncio
import logging
import sys

from app.db.database import init_db, close_db, get_db_session
from app.db.repository import UserRepository, ListeningHistoryRepository
from app.services.spotify import spotify_client
from app.services.spotify_tokens import get_valid_access_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def sync_user(user, db) -> int:
    """Sync one user's recently played tracks. Returns the number of plays fetched."""
    access_token = await get_valid_access_token(user, db)
    if not access_token:
        logger.warning("Skipping user %s: no valid Spotify token", user.id)
        return 0

    plays = await spotify_client.get_user_recently_played(access_token, limit=50)
    if not plays:
        return 0

    genres_by_track = await spotify_client.genres_for_tracks(plays)
    for play in plays:
        play["genres"] = genres_by_track.get(play["spotify_id"], [])

    await ListeningHistoryRepository(db).upsert_many(user.id, plays)
    return len(plays)


async def run() -> None:
    await init_db()
    try:
        async with get_db_session() as db:
            users = await UserRepository(db).list_with_spotify_connected()
            logger.info("Syncing recently played for %d connected users", len(users))

            synced = 0
            for user in users:
                try:
                    count = await sync_user(user, db)
                    synced += count
                except Exception:
                    logger.exception("Failed to sync recently played for user %s", user.id)

            logger.info("Sync complete: %d plays processed across %d users", synced, len(users))
    finally:
        await spotify_client.close()
        await close_db()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception:
        logger.exception("Recently-played sync job failed")
        sys.exit(1)
