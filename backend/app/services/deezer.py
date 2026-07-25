"""
Deezer API client — Layer 3 of audio feature extraction.

Deezer provides BPM and gain (loudness proxy) for tracks via ISRC lookup.
No API key required. Rate limit: ~50 requests per 5 seconds.

Endpoint used:
  GET https://api.deezer.com/track/isrc:{ISRC}

Returns: bpm (float), gain (dBFS proxy), title, artist, duration.
"""

import httpx
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DeezerClient:
    BASE_URL = "https://api.deezer.com"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_track_by_isrc(self, isrc: str) -> Optional[Dict[str, Any]]:
        """
        Look up a track by ISRC code.

        Returns dict with: bpm, gain, title, artist, duration
        Returns None if not found or BPM unavailable.
        """
        if not isrc:
            return None

        client = await self._get_client()

        try:
            response = await client.get(f"{self.BASE_URL}/track/isrc:{isrc}")

            if response.status_code != 200:
                logger.debug(f"Deezer ISRC lookup failed for {isrc}: {response.status_code}")
                return None

            data = response.json()

            if data.get("error") or not data.get("id"):
                logger.debug(f"Deezer: no track found for ISRC {isrc}")
                return None

            bpm = data.get("bpm")
            gain = data.get("gain")

            return {
                "id": data.get("id"),
                "title": data.get("title"),
                "artist": data.get("artist", {}).get("name"),
                "duration": data.get("duration"),
                "bpm": float(bpm) if bpm else None,
                "gain": float(gain) if gain is not None else None,
                "preview_url": data.get("preview"),
            }

        except Exception as e:
            logger.warning(f"Deezer request failed for ISRC {isrc}: {e}")
            return None

    async def get_track_bpm(self, isrc: str) -> Optional[float]:
        """
        Get BPM for a track via ISRC.
        Returns None if not found or BPM is 0 (Deezer returns 0 when unknown).
        """
        track = await self.get_track_by_isrc(isrc)
        if not track:
            return None

        bpm = track.get("bpm")
        if bpm and bpm > 0:
            return bpm
        return None

    async def get_track_loudness(self, isrc: str) -> Optional[float]:
        """
        Get gain (loudness proxy in dBFS) for a track via ISRC.
        Returns None if not found.
        """
        track = await self.get_track_by_isrc(isrc)
        if not track:
            return None

        return track.get("gain")


deezer_client = DeezerClient()
