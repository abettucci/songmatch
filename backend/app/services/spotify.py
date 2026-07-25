"""
Spotify Web API client.

Only uses endpoints verified as available in February 2026:
- GET /search
- GET /tracks/{id} and GET /tracks?ids=...
- GET /artists/{id}
- GET /artists/{id}/related-artists
- GET /artists/{id}/albums
- GET /albums/{id}/tracks

Removed (deprecated/removed by Spotify):
- GET /audio-features (deprecated Nov 27, 2024)
- GET /audio-analysis (deprecated Nov 27, 2024)
- GET /recommendations (deprecated Nov 27, 2024)
- GET /artists/{id}/top-tracks (removed Feb 2026)
"""

import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import logging
import base64
import urllib.parse

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SpotifyClient:
    BASE_URL = "https://api.spotify.com/v1"
    AUTH_URL = "https://accounts.spotify.com/api/token"
    AUTHORIZE_URL = "https://accounts.spotify.com/authorize"

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _ensure_token(self):
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return
        await self._refresh_token()

    async def _refresh_token(self):
        client = await self._get_client()

        credentials = f"{settings.spotify_client_id}:{settings.spotify_client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        response = await client.post(
            self.AUTH_URL,
            headers={
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )

        if response.status_code != 200:
            logger.error(f"Failed to get Spotify token: {response.text}")
            raise Exception("Failed to authenticate with Spotify")

        data = response.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        logger.info("Spotify access token refreshed")

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        await self._ensure_token()
        client = await self._get_client()

        url = f"{self.BASE_URL}{endpoint}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        response = await client.request(
            method, url, headers=headers, params=params, json=json
        )

        if response.status_code == 401:
            await self._refresh_token()
            headers = {"Authorization": f"Bearer {self._access_token}"}
            response = await client.request(
                method, url, headers=headers, params=params, json=json
            )

        if response.status_code != 200:
            logger.warning(f"Spotify API {method} {endpoint}: {response.status_code}")
            return {}

        return response.json()

    async def search_tracks(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        if not query:
            return []

        limit = max(1, min(50, limit))
        data = await self._request(
            "GET",
            "/search",
            params={"q": query, "type": "track", "limit": limit},
        )

        tracks = data.get("tracks", {}).get("items", [])
        return [self._format_track(t) for t in tracks if t]

    async def get_track(self, track_id: str) -> Optional[Dict[str, Any]]:
        if not track_id:
            return None

        data = await self._request("GET", f"/tracks/{track_id}")
        if not data:
            return None

        return self._format_track(data)

    async def get_tracks(self, track_ids: List[str]) -> List[Dict[str, Any]]:
        if not track_ids:
            return []

        track_ids = track_ids[:50]
        data = await self._request(
            "GET", "/tracks", params={"ids": ",".join(track_ids)}
        )

        tracks = data.get("tracks", [])
        return [self._format_track(t) for t in tracks if t]

    async def get_artist(self, artist_id: str) -> Optional[Dict[str, Any]]:
        if not artist_id:
            return None

        data = await self._request("GET", f"/artists/{artist_id}")
        if not data:
            return None

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "genres": data.get("genres", []),
            "popularity": data.get("popularity", 0),
            "image_url": data.get("images", [{}])[0].get("url") if data.get("images") else None,
        }

    async def get_related_artists(self, artist_id: str) -> List[Dict[str, Any]]:
        if not artist_id:
            return []

        data = await self._request("GET", f"/artists/{artist_id}/related-artists")
        artists = data.get("artists", [])
        return [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "genres": a.get("genres", []),
                "popularity": a.get("popularity", 0),
            }
            for a in artists
            if a.get("id")
        ]

    async def get_artist_albums(
        self, artist_id: str, limit: int = 5, include_groups: str = "album,single"
    ) -> List[Dict[str, Any]]:
        """Get artist albums (replaces deprecated top-tracks for candidate discovery)."""
        if not artist_id:
            return []

        data = await self._request(
            "GET",
            f"/artists/{artist_id}/albums",
            params={
                "include_groups": include_groups,
                "limit": min(limit, 20),
                "market": "US",
            },
        )

        items = data.get("items", [])
        return [
            {
                "id": album.get("id"),
                "name": album.get("name"),
                "album_type": album.get("album_type"),
                "total_tracks": album.get("total_tracks", 0),
                "release_date": album.get("release_date"),
                "image_url": album.get("images", [{}])[0].get("url") if album.get("images") else None,
            }
            for album in items
            if album.get("id")
        ]

    async def get_album_tracks(
        self, album_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get tracks from an album for candidate discovery."""
        if not album_id:
            return []

        data = await self._request(
            "GET",
            f"/albums/{album_id}/tracks",
            params={"limit": min(limit, 50), "market": "US"},
        )

        items = data.get("items", [])
        return [
            {
                "id": track.get("id"),
                "name": track.get("name"),
                "artists": [{"id": a.get("id"), "name": a.get("name")} for a in track.get("artists", [])],
                "preview_url": track.get("preview_url"),
                "duration_ms": track.get("duration_ms", 0),
                "track_number": track.get("track_number"),
            }
            for track in items
            if track.get("id")
        ]

    async def get_candidate_tracks(
        self,
        artist_ids: List[str],
        max_per_artist: int = 10,
        require_preview: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Discover candidate tracks from artist IDs via albums.
        Replaces deprecated get_artist_top_tracks.
        """
        import asyncio

        candidates = []
        seen_ids = set()

        async def fetch_artist_tracks(artist_id: str):
            try:
                albums = await self.get_artist_albums(artist_id, limit=3)
                tracks = []
                for album in albums[:2]:
                    album_tracks = await self.get_album_tracks(album["id"], limit=5)
                    tracks.extend(album_tracks)
                return tracks[:max_per_artist]
            except Exception as e:
                logger.warning(f"Failed to fetch tracks for artist {artist_id}: {e}")
                return []

        results = await asyncio.gather(
            *[fetch_artist_tracks(aid) for aid in artist_ids[:5]],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, list):
                for track in result:
                    track_id = track.get("id")
                    if track_id and track_id not in seen_ids:
                        if require_preview and not track.get("preview_url"):
                            continue
                        seen_ids.add(track_id)
                        candidates.append(track)

        return candidates

    async def search_track(self, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """Search for a specific track by artist and title."""
        query = f"artist:{artist} track:{title}"
        results = await self.search_tracks(query, limit=1)
        return results[0] if results else None

    # ──────────────────────────────────────────────────────
    # OAuth Authorization Code Flow (user-level tokens)
    # ──────────────────────────────────────────────────────

    def get_oauth_url(self, state: str) -> str:
        """Build the Spotify authorization URL to redirect the user to."""
        params = {
            "client_id": settings.spotify_client_id,
            "response_type": "code",
            "redirect_uri": settings.spotify_redirect_uri,
            "state": state,
            "scope": "user-top-read user-read-recently-played",
        }
        return self.AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange an authorization code for user access + refresh tokens."""
        client = await self._get_client()
        credentials = f"{settings.spotify_client_id}:{settings.spotify_client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        response = await client.post(
            self.AUTH_URL,
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
            },
        )

        if response.status_code != 200:
            logger.error(f"Spotify token exchange failed: {response.text}")
            raise Exception("Failed to exchange Spotify authorization code")

        return response.json()

    async def refresh_user_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh a user's access token using their refresh token."""
        client = await self._get_client()
        credentials = f"{settings.spotify_client_id}:{settings.spotify_client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        response = await client.post(
            self.AUTH_URL,
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

        if response.status_code != 200:
            logger.error(f"Spotify token refresh failed: {response.text}")
            raise Exception("Failed to refresh Spotify token")

        return response.json()

    async def get_user_top_tracks(
        self, access_token: str, limit: int = 20, time_range: str = "medium_term"
    ) -> List[Dict[str, Any]]:
        """GET /me/top/tracks with a user access token."""
        client = await self._get_client()
        response = await client.get(
            f"{self.BASE_URL}/me/top/tracks",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": min(limit, 50), "time_range": time_range},
        )

        if response.status_code != 200:
            logger.warning(f"get_user_top_tracks failed: {response.status_code}")
            return []

        items = response.json().get("items", [])
        return [self._format_track(t) for t in items if t]

    async def get_user_recently_played(
        self, access_token: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """GET /me/player/recently-played with a user access token."""
        client = await self._get_client()
        response = await client.get(
            f"{self.BASE_URL}/me/player/recently-played",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": min(limit, 50)},
        )

        if response.status_code != 200:
            logger.warning(f"get_user_recently_played failed: {response.status_code}")
            return []

        items = response.json().get("items", [])
        # recently-played wraps tracks in {"track": {...}, "played_at": ...}
        return [self._format_track(item["track"]) for item in items if item.get("track")]

    def _format_track(self, track: Dict[str, Any]) -> Dict[str, Any]:
        if not track:
            return {}

        album = track.get("album", {})
        artists = track.get("artists", [])
        images = album.get("images", [])
        image_url = images[0]["url"] if images else None

        # Extract ISRC for Deezer lookup
        external_ids = track.get("external_ids", {})
        isrc = external_ids.get("isrc")

        return {
            "spotify_id": track.get("id"),  # field name expected by frontend
            "name": track.get("name"),
            "artist": artists[0]["name"] if artists else "Unknown",
            "artist_id": artists[0]["id"] if artists else None,
            "artists": [{"id": a.get("id"), "name": a.get("name")} for a in artists],
            "album": album.get("name", ""),
            "album_id": album.get("id"),
            "album_image": image_url,
            "preview_url": track.get("preview_url"),
            "duration_ms": track.get("duration_ms", 0),
            "popularity": track.get("popularity", 0),
            "external_url": track.get("external_urls", {}).get("spotify", ""),
            "uri": track.get("uri"),
            "isrc": isrc,
        }


spotify_client = SpotifyClient()
