"""
Audio feature extraction — 3-layer architecture.

Layer 1 (always available): librosa over preview audio (30s)
  → tempo, MFCCs, chroma, spectral features, RMS, estimated high-level features

Layer 2 (optional, better valence/energy): Cyanite.ai GraphQL API
  → valence, energyLevel, arousal, BPM, key, timeSignature
  → requires CYANITE_API_KEY

Layer 3 (fast BPM+loudness lookup): Deezer API via ISRC
  → bpm, gain (loudness proxy)
  → no API key required

Enrichment flow inside extract_from_bytes():
  1. Extract base features with librosa (always)
  2. If ISRC → Deezer → overwrite tempo and loudness if better
  3. If preview_url + CYANITE_API_KEY → Cyanite.ai → overwrite valence and energy
"""

import io
import asyncio
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

import httpx
import librosa
import numpy as np

from app.services.deezer import deezer_client
from app.services.cyanite import cyanite_client

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)

LIBROSA_AVAILABLE = True  # librosa is a required dependency


@dataclass
class AudioData:
    # Metadata (needed by structural analysis)
    sample_rate: int = 22050
    hop_length: int = 512
    duration: float = 0.0

    # Temporal scalars
    rms_mean: float = 0.0
    rms_std: float = 0.0
    zcr_mean: float = 0.0

    # Spectral scalars
    spectral_centroid_mean: float = 0.0
    spectral_rolloff_mean: float = 0.0
    spectral_bandwidth_mean: float = 0.0
    spectral_contrast_mean: float = 0.0
    spectral_flatness_mean: float = 0.0

    # Harmonic averages (per-bin means)
    chroma_stft: np.ndarray = field(default_factory=lambda: np.zeros(12))
    chroma_cqt: np.ndarray = field(default_factory=lambda: np.zeros(12))
    chroma_cens: np.ndarray = field(default_factory=lambda: np.zeros(12))
    tonnetz: np.ndarray = field(default_factory=lambda: np.zeros(6))

    # Rhythmic
    tempo: float = 0.0
    beat_regularity: float = 0.0
    onset_strength_mean: float = 0.0

    # Timbre
    mfcc: np.ndarray = field(default_factory=lambda: np.zeros(13))
    mfcc_std: np.ndarray = field(default_factory=lambda: np.zeros(13))

    # High-level (estimated from librosa, may be overwritten by Cyanite/Deezer)
    energy: float = 0.0
    danceability: float = 0.0
    valence: float = 0.5
    arousal: Optional[float] = None
    acousticness: float = 0.0
    instrumentalness: float = 0.0
    speechiness: float = 0.0
    liveness: float = 0.0
    loudness: float = -60.0
    key: Optional[str] = None
    time_signature: Optional[str] = None
    feature_source: str = "librosa"
    genre_tags: list[str] = field(default_factory=list)
    subgenre_tags: list[str] = field(default_factory=list)
    mood_tags: list[str] = field(default_factory=list)
    movement_tags: list[str] = field(default_factory=list)
    character_tags: list[str] = field(default_factory=list)
    instrument_tags: list[str] = field(default_factory=list)
    voice_tags: list[str] = field(default_factory=list)
    transformer_caption: Optional[str] = None

    # Full time-series arrays (used by structural analysis)
    rms_energy: Optional[np.ndarray] = None          # (n_frames,)
    frame_times: Optional[np.ndarray] = None         # (n_frames,)
    mel_spectrogram_db: Optional[np.ndarray] = None  # (128, n_frames), in dB
    chromagram: Optional[np.ndarray] = None          # (12, n_frames), full time series


def _extract_librosa(audio_bytes: bytes) -> AudioData:
    """
    CPU-bound feature extraction via librosa.
    Runs in a ThreadPoolExecutor.
    """
    hop_length = 512
    audio_io = io.BytesIO(audio_bytes)
    y, sr = librosa.load(audio_io, sr=22050, mono=True, duration=30.0)

    if len(y) == 0:
        return AudioData()

    data = AudioData(sample_rate=sr, hop_length=hop_length)
    data.duration = librosa.get_duration(y=y, sr=sr)

    # --- RMS energy (full time series + scalars) ---
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    data.rms_energy = rms
    data.rms_mean = float(np.mean(rms))
    data.rms_std = float(np.std(rms))

    # --- Frame times ---
    data.frame_times = librosa.times_like(rms, sr=sr, hop_length=hop_length)

    # --- ZCR ---
    data.zcr_mean = float(np.mean(librosa.feature.zero_crossing_rate(y, hop_length=hop_length)[0]))

    # --- Spectral scalars ---
    data.spectral_centroid_mean = float(
        np.mean(librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length))
    )
    data.spectral_rolloff_mean = float(
        np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=hop_length))
    )
    data.spectral_bandwidth_mean = float(
        np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop_length))
    )
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=hop_length)
    data.spectral_contrast_mean = float(np.mean(contrast))
    data.spectral_flatness_mean = float(
        np.mean(librosa.feature.spectral_flatness(y=y, hop_length=hop_length))
    )

    # --- Harmonic (full chromagram + averages) ---
    chroma_stft = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=hop_length)
    data.chromagram = chroma_stft                    # (12, n_frames) for SSM
    data.chroma_stft = np.mean(chroma_stft, axis=1)  # (12,) average

    chroma_cqt = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    data.chroma_cqt = np.mean(chroma_cqt, axis=1)

    chroma_cens = librosa.feature.chroma_cens(y=y, sr=sr, hop_length=hop_length)
    data.chroma_cens = np.mean(chroma_cens, axis=1)

    harmonic = librosa.effects.harmonic(y)
    tonnetz = librosa.feature.tonnetz(y=harmonic, sr=sr)
    data.tonnetz = np.mean(tonnetz, axis=1)

    # --- Rhythmic ---
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    data.onset_strength_mean = float(np.mean(onset_env))

    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=hop_length)
    data.tempo = float(tempo) if np.isscalar(tempo) else float(tempo[0])

    if len(beats) > 1:
        beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=hop_length)
        ibi = np.diff(beat_times)
        data.beat_regularity = float(1.0 - min(np.std(ibi) / (np.mean(ibi) + 1e-6), 1.0))
    else:
        data.beat_regularity = 0.0

    # --- Timbre (MFCC) ---
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop_length)
    data.mfcc = np.mean(mfcc, axis=1)
    data.mfcc_std = np.std(mfcc, axis=1)

    # --- Mel spectrogram in dB (for SSM) ---
    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, hop_length=hop_length)
    data.mel_spectrogram_db = librosa.power_to_db(mel, ref=np.max)  # (128, n_frames)

    # --- High-level estimates ---
    rms_ref = 0.1
    data.energy = float(np.clip(data.rms_mean / rms_ref, 0.0, 1.0))

    onset_norm = float(np.clip(data.onset_strength_mean / 5.0, 0.0, 1.0))
    data.danceability = float(np.clip(
        data.beat_regularity * 0.4 + data.energy * 0.3 + onset_norm * 0.3,
        0.0, 1.0,
    ))

    major_bins = [0, 2, 4, 5, 7, 9, 11]
    major_energy = float(np.mean(data.chroma_stft[major_bins]))
    brightness = float(np.clip(data.spectral_centroid_mean / (sr / 2), 0.0, 1.0))
    data.valence = float(np.clip(major_energy * 0.6 + brightness * 0.4, 0.0, 1.0))

    flatness_inv = float(1.0 - np.clip(data.spectral_flatness_mean * 100, 0.0, 1.0))
    bandwidth_norm = float(np.clip(data.spectral_bandwidth_mean / (sr / 2), 0.0, 1.0))
    data.acousticness = float(np.clip(flatness_inv * 0.6 + (1.0 - bandwidth_norm) * 0.4, 0.0, 1.0))

    zcr_norm = float(np.clip(data.zcr_mean * 10, 0.0, 1.0))
    mfcc2_norm = float(np.clip(abs(data.mfcc[1]) / 50.0, 0.0, 1.0))
    data.speechiness = float(np.clip(zcr_norm * 0.5 + mfcc2_norm * 0.5, 0.0, 1.0))
    data.instrumentalness = float(np.clip(1.0 - data.speechiness, 0.0, 1.0))

    contrast_norm = float(np.clip(data.spectral_contrast_mean / 20.0, 0.0, 1.0))
    data.liveness = float(np.clip(contrast_norm * 0.7 + data.rms_std * 3.0 * 0.3, 0.0, 1.0))

    if data.rms_mean > 0:
        data.loudness = float(20.0 * math.log10(data.rms_mean))
    else:
        data.loudness = -60.0

    return data


class AudioFeatureExtractor:
    """
    Extracts audio features using a 3-layer strategy:
    Layer 1: librosa (always)
    Layer 2: Cyanite.ai (optional, for valence/energy)
    Layer 3: Deezer (optional, for BPM/loudness via ISRC)
    """

    async def extract_from_bytes(
        self,
        audio_bytes: bytes,
        isrc: Optional[str] = None,
        preview_url: Optional[str] = None,
        spotify_id: Optional[str] = None,
    ) -> AudioData:
        """Extract features from raw audio bytes with optional enrichment."""
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_executor, _extract_librosa, audio_bytes)
        await self._enrich(data, isrc=isrc, preview_url=preview_url, spotify_id=spotify_id)
        return data

    async def extract_from_url(
        self,
        url: str,
        isrc: Optional[str] = None,
        spotify_id: Optional[str] = None,
    ) -> Optional[AudioData]:
        """Download audio from URL and extract features."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(f"Failed to download audio from {url}: {response.status_code}")
                    return None
                audio_bytes = response.content
        except Exception as e:
            logger.warning(f"Failed to download audio from {url}: {e}")
            return None

        return await self.extract_from_bytes(
            audio_bytes,
            isrc=isrc,
            preview_url=url,
            spotify_id=spotify_id,
        )

    async def _enrich(
        self,
        data: AudioData,
        isrc: Optional[str] = None,
        preview_url: Optional[str] = None,
        spotify_id: Optional[str] = None,
    ) -> None:
        tasks = []
        if isrc:
            tasks.append(self._enrich_from_deezer(data, isrc))
        if spotify_id:
            tasks.append(self._enrich_from_cyanite_spotify(data, spotify_id))
        if preview_url and not spotify_id:
            tasks.append(self._enrich_from_cyanite(data, preview_url))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _enrich_from_deezer(self, data: AudioData, isrc: str) -> None:
        try:
            track = await deezer_client.get_track_by_isrc(isrc)
            if not track:
                return
            deezer_bpm = track.get("bpm")
            if deezer_bpm and deezer_bpm > 0:
                data.tempo = float(deezer_bpm)
                logger.debug(f"Enriched tempo from Deezer: {deezer_bpm} BPM")
            deezer_gain = track.get("gain")
            if deezer_gain is not None:
                data.loudness = float(deezer_gain)
                logger.debug(f"Enriched loudness from Deezer: {deezer_gain} dBFS")
        except Exception as e:
            logger.debug(f"Deezer enrichment failed: {e}")

    async def _apply_cyanite_features(self, data: AudioData, features) -> None:
        if features.valence is not None:
            data.valence = float(np.clip(features.valence, 0.0, 1.0))
            logger.debug(f"Enriched valence from Cyanite.ai: {features.valence}")
        if features.energy_level is not None:
            data.energy = float(np.clip(features.energy_level, 0.0, 1.0))
            logger.debug(f"Enriched energy from Cyanite.ai: {features.energy_level}")
        if features.arousal is not None:
            data.arousal = float(np.clip(features.arousal, 0.0, 1.0))
        if features.bpm and features.bpm > 0:
            data.tempo = float(features.bpm)
        data.key = features.key or data.key
        data.time_signature = features.time_signature or data.time_signature
        data.feature_source = features.provider
        data.genre_tags = features.genre_tags or data.genre_tags
        data.subgenre_tags = features.subgenre_tags or data.subgenre_tags
        data.mood_tags = features.mood_tags or data.mood_tags
        data.movement_tags = features.movement_tags or data.movement_tags
        data.character_tags = features.character_tags or data.character_tags
        data.instrument_tags = features.instrument_tags or data.instrument_tags
        data.voice_tags = features.voice_tags or data.voice_tags
        data.transformer_caption = features.transformer_caption or data.transformer_caption

    async def _enrich_from_cyanite_spotify(self, data: AudioData, spotify_id: str) -> None:
        try:
            features = await cyanite_client.analyze_spotify_track(spotify_id)
            if features and features.status == "finished":
                await self._apply_cyanite_features(data, features)
        except Exception as e:
            logger.debug(f"Cyanite Spotify enrichment failed: {e}")

    async def _enrich_from_cyanite(self, data: AudioData, preview_url: str) -> None:
        try:
            features = await cyanite_client.analyze_preview(preview_url)
            if not features:
                return
            await self._apply_cyanite_features(data, features)
        except Exception as e:
            logger.debug(f"Cyanite enrichment failed: {e}")

    def to_feature_vector(self, data: AudioData) -> np.ndarray:
        """Compact feature vector for cosine similarity in recommendations."""
        tempo_norm = float(np.clip(data.tempo / 200.0, 0.0, 1.0))
        mfcc_mean = float(np.mean(np.abs(data.mfcc)) / 100.0)
        chroma_mean = float(np.mean(data.chroma_stft))

        return np.array([
            data.energy,
            data.valence,
            tempo_norm,
            data.danceability,
            data.acousticness,
            mfcc_mean,
            chroma_mean,
            float(np.clip(data.loudness / -60.0, 0.0, 1.0)),
        ], dtype=np.float32)


# Singleton
audio_extractor = AudioFeatureExtractor()

# Alias for backward compatibility
audio_feature_extractor = audio_extractor
