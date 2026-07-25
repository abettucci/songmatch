"""
FastAPI application entry point.

Fixes:
- CORS origins: use explicit settings.cors_origins only (no wildcard https://* — Bug #9)
- Mangum lifespan="auto" in lambda_handler.py (not "off" — Bug #5)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys

from app.core.config import get_settings
from app.db.database import init_db, close_db
from app.services.spotify import spotify_client
from app.services.lastfm import lastfm_client
from app.services.deezer import deezer_client
from app.services.cyanite import cyanite_client
from app.services.clap_embeddings import clap_service
from app.api.routes import router
from app.api.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize DB and close external clients on shutdown."""
    logger.info("Starting SongMatch API...")
    await init_db()
    logger.info("SongMatch API started successfully")

    yield

    logger.info("Shutting down SongMatch API...")
    await spotify_client.close()
    await lastfm_client.close()
    await deezer_client.close()
    await cyanite_client.close()
    await clap_service.close()
    await close_db()
    logger.info("SongMatch API shut down")


app = FastAPI(
    title=settings.app_name,
    description="Music recommendation API with multiple algorithms",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: only allow explicitly configured origins (no wildcard — Bug #9 fix)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=300,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_window=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "running",
    }
