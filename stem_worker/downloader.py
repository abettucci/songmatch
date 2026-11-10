"""Acquire Spotify-resolved or user-uploaded audio in a private job directory."""

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import httpx
from mutagen import File as MutagenFile

SPOTIFY_HOST = "open.spotify.com"
SPOTIFY_TRACK_PATH = re.compile(r"^/track/[A-Za-z0-9]{22}/?$")
MAX_AUDIO_SECONDS = 10 * 60
MAX_AUDIO_BYTES = 100 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 180
SPOTIFY_AUDIO_PROVIDERS = ("youtube-music", "youtube")


class AudioSourceError(Exception):
    pass


class InvalidAudioError(AudioSourceError):
    pass


def validate_spotify_url(url: str) -> None:
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise AudioSourceError("invalid source") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != SPOTIFY_HOST
        or parsed.username
        or parsed.password
        or not SPOTIFY_TRACK_PATH.fullmatch(parsed.path)
    ):
        raise AudioSourceError("invalid source")


def validate_audio_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0 or path.stat().st_size > MAX_AUDIO_BYTES:
        raise InvalidAudioError("invalid audio")
    try:
        metadata = MutagenFile(path)
        duration = float(metadata.info.length) if metadata and metadata.info else 0
    except (OSError, AttributeError, TypeError, ValueError) as exc:
        raise InvalidAudioError("invalid audio") from exc
    if duration <= 0 or duration > MAX_AUDIO_SECONDS:
        raise InvalidAudioError("invalid audio")


def download_spotify(url: str, output_dir: Path) -> Path:
    validate_spotify_url(url)
    output_template = output_dir / "%(track-id)s.%(output-ext)s"
    command = [
        "spotdl", "download", url,
        "--output", str(output_template),
        "--format", "mp3",
        "--audio", *SPOTIFY_AUDIO_PROVIDERS,
        "--max-retries", "0",
        "--no-cache",
        "--print-errors",
    ]
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if client_id and client_secret:
        command.extend(["--client-id", client_id, "--client-secret", client_secret])

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            cwd=output_dir,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
            shell=False,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise AudioSourceError("source unavailable") from exc

    audio_files = sorted(output_dir.glob("*.mp3"), key=lambda file: file.stat().st_mtime, reverse=True)
    if not audio_files:
        raise AudioSourceError("source unavailable")
    audio_path = audio_files[0]
    validate_audio_file(audio_path)
    return audio_path


def download_upload(url: str, output_dir: Path, bucket: str, region: str) -> Path:
    parsed = urlparse(url)
    allowed_hosts = {
        f"{bucket}.s3.{region}.amazonaws.com",
        f"{bucket}.s3.amazonaws.com",
        f"s3.{region}.amazonaws.com",
    }
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or not parsed.query:
        raise AudioSourceError("invalid source")

    extension = Path(parsed.path).suffix.casefold()
    if extension not in {".mp3", ".wav", ".m4a"}:
        raise AudioSourceError("invalid source")
    audio_path = output_dir / f"uploaded-audio{extension}"
    total = 0
    try:
        with httpx.stream("GET", url, timeout=60, follow_redirects=False) as response:
            response.raise_for_status()
            content_length = int(response.headers.get("content-length", "0"))
            if content_length > MAX_AUDIO_BYTES:
                raise AudioSourceError("invalid audio")
            with audio_path.open("wb") as destination:
                for chunk in response.iter_bytes(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_AUDIO_BYTES:
                        raise AudioSourceError("invalid audio")
                    destination.write(chunk)
    except AudioSourceError:
        raise
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise AudioSourceError("source unavailable") from exc
    validate_audio_file(audio_path)
    return audio_path
