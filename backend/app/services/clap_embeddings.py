"""
CLAP (Contrastive Language-Audio Pretraining) embedding service.

Model: laion/larger_clap_music — ~335 MB, downloaded once to ~/.cache/huggingface/
Output: 512-dim L2-normalized vectors per 30s preview

First call loads the model (5-15s). Subsequent calls use the in-memory cache.
Inference runs in a thread pool executor (CPU-bound) so it doesn't block the event loop.

Install dependencies before use:
    pip install transformers
    pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only (~220 MB)
"""

import asyncio
import io
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import numpy as np
import httpx

logger = logging.getLogger(__name__)

# Thread pool: CLAP inference is CPU-bound, 2 workers is enough
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="clap_worker")

# In-memory cache: preview_url -> L2-normalized 512-dim embedding
_embedding_cache: dict[str, np.ndarray] = {}

# Lazy-loaded model (initialized on first embed call)
_clap_model = None
_clap_processor = None
_model_load_attempted = False


def _load_clap_model():
    """Load CLAP model. Called once from the thread pool."""
    global _clap_model, _clap_processor, _model_load_attempted
    if _model_load_attempted:
        return _clap_model, _clap_processor

    _model_load_attempted = True
    try:
        from transformers import ClapModel, ClapProcessor

        model_name = "laion/larger_clap_music"
        logger.info(f"Loading CLAP model '{model_name}' (first use — downloads ~335 MB if not cached)...")
        _clap_processor = ClapProcessor.from_pretrained(model_name)
        _clap_model = ClapModel.from_pretrained(model_name)
        _clap_model.eval()
        logger.info("CLAP model loaded successfully.")
    except ImportError:
        logger.error(
            "torch/transformers not installed. Run:\n"
            "  pip install transformers\n"
            "  pip install torch --index-url https://download.pytorch.org/whl/cpu"
        )
    except Exception as exc:
        logger.error(f"Failed to load CLAP model: {exc}")

    return _clap_model, _clap_processor


def _embed_audio_sync(audio_bytes: bytes) -> Optional[np.ndarray]:
    """
    CPU-bound: decode audio bytes → CLAP embedding.
    Runs in thread pool so it doesn't block asyncio.
    """
    try:
        import librosa
        import torch

        model, processor = _load_clap_model()
        if model is None or processor is None:
            return None

        # CLAP requires 48 kHz mono audio
        audio_array, _ = librosa.load(io.BytesIO(audio_bytes), sr=48000, mono=True)

        inputs = processor(
            audios=audio_array,
            return_tensors="pt",
            sampling_rate=48000,
            padding=True,
        )
        with torch.no_grad():
            audio_features = model.get_audio_features(**inputs)

        embedding = audio_features.numpy()[0]  # shape: (512,)

        # L2-normalize → cosine similarity = dot product
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding.astype(np.float32)

    except Exception as exc:
        logger.warning(f"CLAP embedding failed: {exc}")
        return None


class CLAPEmbeddingService:
    """
    Async wrapper around CLAP inference.

    Usage:
        embedding = await clap_service.embed_from_url(preview_url)
        # Returns np.ndarray of shape (512,), L2-normalized.
        # Returns None if torch is not installed or download fails.
    """

    def __init__(self):
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=20.0)
        return self._http

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None

    async def embed_from_url(self, url: str) -> Optional[np.ndarray]:
        """
        Download a Spotify preview URL and compute its CLAP embedding.
        Result is cached in memory by URL.
        """
        if url in _embedding_cache:
            return _embedding_cache[url]

        # Download preview
        try:
            client = await self._get_http()
            response = await client.get(url)
            if response.status_code != 200:
                logger.warning(f"Preview download failed ({response.status_code}): {url}")
                return None
            audio_bytes = response.content
        except Exception as exc:
            logger.warning(f"Preview download error: {exc}")
            return None

        # Run CPU inference off the event loop
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(_executor, _embed_audio_sync, audio_bytes)

        if embedding is not None:
            _embedding_cache[url] = embedding
            logger.debug(f"CLAP embedding cached for {url[:60]}...")

        return embedding

    def cache_size(self) -> int:
        return len(_embedding_cache)


clap_service = CLAPEmbeddingService()
