from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional, List
import json


class Settings(BaseSettings):
    # Application
    app_name: str = "SoundMatch API"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Database
    database_url: str = ""
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # JWT Authentication
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_days: int = 7

    # Spotify API
    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    # Last.fm API
    lastfm_api_key: str = ""

    # Cyanite.ai API (optional - improves valence/energy quality)
    cyanite_api_key: str = ""

    # Spotify OAuth redirect URI
    spotify_redirect_uri: str = "http://localhost:8080/api/v1/auth/spotify/callback"

    # Frontend URL (used for OAuth redirects after Spotify callback)
    frontend_url: str = "http://localhost:5173"

    # Rate Limiting
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # CORS — stored as plain str so pydantic-settings never tries to JSON-decode it.
    # Accepts comma-separated URLs or a JSON array string.
    # Example: CORS_ORIGINS=http://localhost:5173,http://localhost:8080
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def cors_origins_list(self) -> List[str]:
        v = self.cors_origins.strip()
        if not v:
            return ["http://localhost:5173", "http://localhost:8080"]
        if v.startswith('['):
            return json.loads(v)
        return [origin.strip() for origin in v.split(',') if origin.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
