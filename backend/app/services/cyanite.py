"""
Cyanite.ai GraphQL API client — optional Layer 2 of feature extraction.

Uses Audio Analysis V7 for Spotify tracks when CYANITE_API_KEY is configured.
If the account is not authorized for Spotify audio analysis, the track is still
processed by local librosa/Deezer fallbacks.
"""

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

GRAPHQL_URL = "https://api.cyanite.ai/graphql"
MAX_POLL_ATTEMPTS = 6
POLL_INTERVAL_SECONDS = 5.0
ENERGY_LEVEL_TO_SCORE = {
    "low": 0.25,
    "medium": 0.55,
    "high": 0.9,
    "variable": 0.65,
}


@dataclass
class CyaniteFeatures:
    valence: Optional[float] = None
    energy_level: Optional[float] = None
    arousal: Optional[float] = None
    bpm: Optional[float] = None
    key: Optional[str] = None
    time_signature: Optional[str] = None
    status: str = "unknown"
    provider: str = "cyanite_v7"
    energy_label: Optional[str] = None
    energy_dynamics: Optional[str] = None
    genre_tags: List[str] = field(default_factory=list)
    subgenre_tags: List[str] = field(default_factory=list)
    mood_tags: List[str] = field(default_factory=list)
    movement_tags: List[str] = field(default_factory=list)
    character_tags: List[str] = field(default_factory=list)
    instrument_tags: List[str] = field(default_factory=list)
    voice_tags: List[str] = field(default_factory=list)
    transformer_caption: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CyaniteClient:
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    def _is_configured(self) -> bool:
        return bool(settings.cyanite_api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _graphql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        client = await self._get_client()
        headers = {
            "Authorization": f"Bearer {settings.cyanite_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"query": query, "variables": variables}

        response = await client.post(GRAPHQL_URL, headers=headers, json=payload)

        if response.status_code != 200:
            logger.warning(f"Cyanite API error: {response.status_code} - {response.text}")
            return {}

        body = response.json()
        if "errors" in body:
            logger.warning(f"Cyanite GraphQL errors: {body['errors']}")
            return {}

        return body.get("data", {})

    def _normalize_energy_level(self, label: Optional[str]) -> Optional[float]:
        if not label:
            return None
        return ENERGY_LEVEL_TO_SCORE.get(str(label).lower())

    def _merge_tags(self, *tag_lists: Optional[List[str]]) -> List[str]:
        tags: List[str] = []
        seen = set()
        for tag_list in tag_lists:
            for tag in tag_list or []:
                normalized = str(tag).strip()
                key = normalized.lower()
                if normalized and key not in seen:
                    tags.append(normalized)
                    seen.add(key)
        return tags

    def _from_v7_result(self, result: Dict[str, Any]) -> CyaniteFeatures:
        bpm_prediction = result.get("bpmPrediction") or {}
        key_prediction = result.get("keyPrediction") or {}
        energy_label = result.get("energyLevel")

        return CyaniteFeatures(
            valence=result.get("valence"),
            energy_level=self._normalize_energy_level(energy_label),
            arousal=result.get("arousal"),
            bpm=(
                result.get("bpmRangeAdjusted")
                or bpm_prediction.get("value")
            ),
            key=key_prediction.get("value"),
            time_signature=result.get("timeSignature"),
            status="finished",
            energy_label=energy_label,
            energy_dynamics=result.get("energyDynamics"),
            genre_tags=self._merge_tags(
                result.get("genreTags"),
                result.get("advancedGenreTags"),
            ),
            subgenre_tags=self._merge_tags(
                result.get("subgenreTags"),
                result.get("advancedSubgenreTags"),
            ),
            mood_tags=self._merge_tags(
                result.get("moodTags"),
                result.get("moodAdvancedTags"),
            ),
            movement_tags=self._merge_tags(result.get("movementTags")),
            character_tags=self._merge_tags(result.get("characterTags")),
            instrument_tags=self._merge_tags(
                result.get("instrumentTags"),
                result.get("advancedInstrumentTags"),
                result.get("advancedInstrumentTagsExtended"),
            ),
            voice_tags=self._merge_tags(result.get("voiceTags")),
            transformer_caption=result.get("transformerCaption"),
            raw=result,
        )

    def _analysis_selection(self) -> str:
        return """
        audioAnalysisV7 {
          __typename
          ... on AudioAnalysisV7Finished {
            result {
              valence
              arousal
              energyLevel
              energyDynamics
              bpmRangeAdjusted
              bpmPrediction {
                value
                confidence
              }
              keyPrediction {
                value
                confidence
              }
              timeSignature
              genreTags
              subgenreTags
              moodTags
              movementTags
              characterTags
              instrumentTags
              voiceTags
            }
          }
          ... on AudioAnalysisV7Failed {
            error {
              message
            }
          }
          ... on AudioAnalysisV7NotAuthorized {
            message
          }
        }
        """

    def _parse_analysis(self, analysis: Dict[str, Any]) -> Optional[CyaniteFeatures]:
        typename = analysis.get("__typename")
        if typename == "AudioAnalysisV7Finished":
            return self._from_v7_result(analysis.get("result") or {})
        if typename in {"AudioAnalysisV7Processing", "AudioAnalysisV7Enqueued", "AudioAnalysisV7NotStarted"}:
            return CyaniteFeatures(status="processing")
        if typename == "AudioAnalysisV7NotAuthorized":
            logger.info("Cyanite Spotify audio analysis is not authorized for this account")
            return CyaniteFeatures(status="not_authorized")
        if typename == "AudioAnalysisV7Failed":
            error = analysis.get("error") or {}
            logger.warning(f"Cyanite V7 analysis failed: {error.get('message')}")
            return CyaniteFeatures(status="failed")
        return None

    async def _query_spotify_track(self, spotify_track_id: str) -> Optional[CyaniteFeatures]:
        query = f"""
        query SpotifyTrackQuery($id: ID!) {{
          spotifyTrack(id: $id) {{
            __typename
            ... on SpotifyTrack {{
              id
              title
              {self._analysis_selection()}
            }}
            ... on Error {{
              message
            }}
          }}
        }}
        """
        data = await self._graphql(query, {"id": spotify_track_id})
        track = data.get("spotifyTrack") or {}
        if track.get("__typename") != "SpotifyTrack":
            message = track.get("message")
            if message:
                logger.warning(f"Cyanite Spotify track query failed: {message}")
            return None
        return self._parse_analysis(track.get("audioAnalysisV7") or {})

    async def _enqueue_spotify_track(self, spotify_track_id: str) -> Optional[CyaniteFeatures]:
        mutation = f"""
        mutation SpotifyTrackEnqueue($input: SpotifyTrackEnqueueInput!) {{
          spotifyTrackEnqueue(input: $input) {{
            __typename
            ... on SpotifyTrackEnqueueSuccess {{
              enqueuedSpotifyTrack {{
                id
                {self._analysis_selection()}
              }}
            }}
            ... on Error {{
              message
            }}
          }}
        }}
        """
        data = await self._graphql(
            mutation,
            {"input": {"spotifyTrackId": spotify_track_id}},
        )
        result = data.get("spotifyTrackEnqueue") or {}
        if result.get("__typename") != "SpotifyTrackEnqueueSuccess":
            message = result.get("message")
            if message:
                logger.warning(f"Cyanite Spotify enqueue failed: {message}")
            return None

        track = result.get("enqueuedSpotifyTrack") or {}
        return self._parse_analysis(track.get("audioAnalysisV7") or {})

    async def analyze_spotify_track(self, spotify_track_id: str) -> Optional[CyaniteFeatures]:
        """
        Analyze a Spotify track through Cyanite Audio Analysis V7.

        Returns finished features when available. If the track is processing or
        the account lacks permission, returns None so local extraction can carry on.
        """
        if not self._is_configured() or not spotify_track_id:
            return None

        try:
            features = await self._query_spotify_track(spotify_track_id)
            if features and features.status == "finished":
                return features

            if not features or features.status in {"processing", "unknown"}:
                features = await self._enqueue_spotify_track(spotify_track_id)

            for _ in range(MAX_POLL_ATTEMPTS):
                if features and features.status == "finished":
                    return features
                if features and features.status in {"failed", "not_authorized"}:
                    return None
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                features = await self._query_spotify_track(spotify_track_id)

            return None
        except Exception as e:
            logger.warning(f"Cyanite Spotify analysis failed for {spotify_track_id}: {e}")
            return None

    async def _upload_by_url(self, preview_url: str) -> Optional[str]:
        """Legacy preview-url upload fallback for accounts that still support it."""
        mutation = """
        mutation AudioFileUploadByUrl($input: AudioFileUploadByUrlInput!) {
          audioFileUploadByUrl(input: $input) {
            ... on AudioFileUploadByUrlSuccess {
              audioFile {
                id
              }
            }
            ... on Error {
              message
            }
          }
        }
        """
        data = await self._graphql(mutation, {"input": {"url": preview_url}})
        result = data.get("audioFileUploadByUrl", {})

        audio_file = result.get("audioFile")
        if audio_file:
            return audio_file.get("id")

        message = result.get("message")
        if message:
            logger.warning(f"Cyanite upload error: {message}")
        return None

    async def _poll_for_analysis(self, audio_file_id: str) -> Optional[Dict[str, Any]]:
        """Legacy poller for pre-V7 preview URL analysis."""
        query = """
        query AudioFile($id: ID!) {
          audioFile(id: $id) {
            ... on AudioFile {
              id
              analysisStatus
              openAiInference {
                ... on AudioFileOpenAiInferenceResult {
                  valence
                  energyLevel
                  arousal
                  bpm
                  keyPrediction {
                    value
                    confidence
                  }
                  timeSignature
                }
              }
            }
            ... on AudioFileNotFoundError {
              message
            }
          }
        }
        """
        for attempt in range(MAX_POLL_ATTEMPTS):
            data = await self._graphql(query, {"id": audio_file_id})
            audio_file = data.get("audioFile", {})

            status = audio_file.get("analysisStatus")
            if status == "finished":
                return audio_file.get("openAiInference")
            elif status == "failed":
                logger.warning(f"Cyanite analysis failed for file {audio_file_id}")
                return None
            elif status in ("queued", "processing"):
                logger.debug(f"Cyanite: attempt {attempt + 1}/{MAX_POLL_ATTEMPTS}, status={status}")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            else:
                logger.warning(f"Cyanite: unknown status {status}")
                return None

        logger.warning(f"Cyanite: analysis timed out for file {audio_file_id}")
        return None

    async def analyze_preview(self, preview_url: str) -> Optional[CyaniteFeatures]:
        """
        Legacy preview URL analysis. Prefer analyze_spotify_track when a
        Spotify ID is available.
        """
        if not self._is_configured():
            return None

        if not preview_url:
            return None

        try:
            audio_file_id = await self._upload_by_url(preview_url)
            if not audio_file_id:
                return None

            inference = await self._poll_for_analysis(audio_file_id)
            if not inference:
                return None

            key_prediction = inference.get("keyPrediction", {}) or {}
            energy_value = inference.get("energyLevel")

            return CyaniteFeatures(
                valence=inference.get("valence"),
                energy_level=(
                    energy_value
                    if isinstance(energy_value, (int, float))
                    else self._normalize_energy_level(energy_value)
                ),
                arousal=inference.get("arousal"),
                bpm=inference.get("bpm"),
                key=key_prediction.get("value"),
                time_signature=inference.get("timeSignature"),
            )

        except Exception as e:
            logger.warning(f"Cyanite analysis failed for {preview_url}: {e}")
            return None


cyanite_client = CyaniteClient()
