"""
Last.fm API client.

Available endpoints (verified Feb 2026):
- artist.getSimilar   → similar artists (WORKING)
- artist.getTopTracks → top tracks for an artist (WORKING)
- artist.getInfo      → artist metadata (WORKING)
- track.getInfo       → track metadata (WORKING)

Removed (broken/deprecated):
- track.getSimilar    → broken since early 2025 (no official fix)
"""

import httpx
from typing import Optional, List, Dict, Any
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LastFMClient:
    BASE_URL = "http://ws.audioscrobbler.com/2.0/"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not settings.lastfm_api_key:
            logger.warning("Last.fm API key not configured")
            return {}

        client = await self._get_client()

        params.update({
            "api_key": settings.lastfm_api_key,
            "format": "json",
            "method": method,
        })

        try:
            response = await client.get(self.BASE_URL, params=params)

            if response.status_code != 200:
                logger.error(f"Last.fm API error: {response.status_code} - {response.text}")
                return {}

            return response.json()
        except Exception as e:
            logger.error(f"Last.fm request failed: {e}")
            return {}

    async def get_similar_artists(self, artist: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get artists similar to the given artist. (WORKING as of Feb 2026)"""
        data = await self._request(
            "artist.getsimilar",
            {
                "artist": artist,
                "limit": limit,
                "autocorrect": 1,
            },
        )

        similar_artists = data.get("similarartists", {}).get("artist", [])

        if isinstance(similar_artists, dict):
            similar_artists = [similar_artists]

        return [
            {
                "name": a.get("name"),
                "match": float(a.get("match", 0)),
                "url": a.get("url"),
            }
            for a in similar_artists
            if a.get("name")
        ]

    async def get_artist_top_tracks(self, artist: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top tracks for an artist. (WORKING as of Feb 2026)"""
        data = await self._request(
            "artist.getTopTracks",
            {
                "artist": artist,
                "limit": limit,
                "autocorrect": 1,
            },
        )

        tracks = data.get("toptracks", {}).get("track", [])

        if isinstance(tracks, dict):
            tracks = [tracks]

        return [
            {
                "name": t.get("name"),
                "artist": artist,
                "playcount": int(t.get("playcount", 0)) if t.get("playcount") else 0,
                "listeners": int(t.get("listeners", 0)) if t.get("listeners") else 0,
                "url": t.get("url"),
                "rank": int(t.get("@attr", {}).get("rank", 0)),
            }
            for t in tracks
            if t.get("name")
        ]

    async def get_track_info(self, artist: str, track: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific track."""
        data = await self._request(
            "track.getInfo",
            {
                "artist": artist,
                "track": track,
                "autocorrect": 1,
            },
        )

        track_info = data.get("track")
        if not track_info:
            return None

        return {
            "name": track_info.get("name"),
            "artist": track_info.get("artist", {}).get("name"),
            "album": track_info.get("album", {}).get("title"),
            "duration": int(track_info.get("duration", 0)),
            "listeners": int(track_info.get("listeners", 0)),
            "playcount": int(track_info.get("playcount", 0)),
            "tags": [
                tag.get("name")
                for tag in track_info.get("toptags", {}).get("tag", [])
            ],
            "url": track_info.get("url"),
        }

    async def get_artist_info(self, artist: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an artist."""
        data = await self._request(
            "artist.getInfo",
            {
                "artist": artist,
                "autocorrect": 1,
            },
        )

        artist_info = data.get("artist")
        if not artist_info:
            return None

        return {
            "name": artist_info.get("name"),
            "listeners": int(artist_info.get("stats", {}).get("listeners", 0)),
            "playcount": int(artist_info.get("stats", {}).get("playcount", 0)),
            "tags": [
                tag.get("name")
                for tag in artist_info.get("tags", {}).get("tag", [])
            ],
            "similar": [
                {
                    "name": a.get("name"),
                    "url": a.get("url"),
                }
                for a in artist_info.get("similar", {}).get("artist", [])
            ],
            "bio": artist_info.get("bio", {}).get("summary", ""),
            "url": artist_info.get("url"),
        }


lastfm_client = LastFMClient()
