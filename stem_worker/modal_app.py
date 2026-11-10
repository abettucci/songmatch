"""Modal GPU worker and authenticated HTTP dispatcher for Songmatch stems."""

import hmac
import json
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

import httpx
import modal
from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

app = modal.App("songmatch-stem-worker")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("songmatch.stem_worker")
STEMS = ("vocals", "drums", "bass", "other", "guitar", "piano")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "curl", "unzip")
    .run_commands("curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh")
    .pip_install(
        "httpx>=0.27",
        "mutagen>=1.47",
        "yt-dlp[default,curl-cffi]>=2025.9.5",
        "spotdl==4.4.3",
        "numpy<2",
        "demucs==4.0.1",
        "fastapi[standard]",
    )
    .add_local_python_source("stem_worker.downloader", "stem_worker.separator")
)


class StemWorkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    source_type: Literal["spotify", "upload"]
    spotify_url: str | None = Field(default=None, max_length=2048)
    source_download_url: HttpUrl | None = None
    output_upload_urls: dict[str, HttpUrl]
    status_upload_url: HttpUrl

    @model_validator(mode="after")
    def validate_request(self):
        if set(self.output_upload_urls) != set(STEMS):
            raise ValueError("All six output destinations are required")
        if self.source_type == "spotify":
            parsed = urlparse(self.spotify_url or "")
            if (
                parsed.scheme != "https"
                or parsed.hostname != "open.spotify.com"
                or parsed.username
                or parsed.password
                or not re.fullmatch(r"/track/[A-Za-z0-9]{22}/?", parsed.path)
                or self.source_download_url is not None
            ):
                raise ValueError("Invalid Spotify source")
        elif self.spotify_url is not None or self.source_download_url is None:
            raise ValueError("An uploaded source is required")

        bucket = os.getenv("STEM_ARTIFACTS_BUCKET", "")
        region = os.getenv("AWS_REGION", "us-east-1")
        allowed_hosts = {
            f"{bucket}.s3.{region}.amazonaws.com",
            f"{bucket}.s3.amazonaws.com",
            f"s3.{region}.amazonaws.com",
        }
        signed_urls = [self.status_upload_url, *self.output_upload_urls.values()]
        if self.source_download_url:
            signed_urls.append(self.source_download_url)
        for signed_url in signed_urls:
            parsed = urlparse(str(signed_url))
            if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or not parsed.query:
                raise ValueError("Invalid artifact destination")
        return self


def _write_status(url: str, status: str, error_code: str | None = None) -> None:
    document = json.dumps({"status": status, "error_code": error_code}, separators=(",", ":"))
    response = httpx.put(
        url,
        content=document,
        headers={"Content-Type": "application/json"},
        timeout=30,
        follow_redirects=False,
    )
    response.raise_for_status()


def _upload_output(url: str, output_path: Path) -> None:
    response = httpx.put(
        url,
        content=output_path.read_bytes(),
        headers={"Content-Type": "audio/mpeg"},
        timeout=300,
        follow_redirects=False,
    )
    response.raise_for_status()


@app.function(
    image=image,
    gpu="T4",
    timeout=1200,
    secrets=[modal.Secret.from_name("songmatch-stem-worker")],
)
def process_song(payload: dict) -> None:
    from stem_worker.downloader import AudioSourceError, InvalidAudioError, download_spotify, download_upload
    from stem_worker.separator import separate_all

    job_id = str(payload["job_id"])
    status_url = payload["status_upload_url"]
    error_code = "separation_failed"
    work_dir = Path(tempfile.mkdtemp(prefix="songmatch-stems-"))
    try:
        if payload["source_type"] == "spotify":
            error_code = "source_unavailable"
            audio_path = download_spotify(payload["spotify_url"], work_dir)
        else:
            error_code = "source_unavailable"
            audio_path = download_upload(
                payload["source_download_url"],
                work_dir,
                os.environ["STEM_ARTIFACTS_BUCKET"],
                os.getenv("AWS_REGION", "us-east-1"),
            )

        _write_status(status_url, "processing")
        error_code = "separation_failed"
        output_paths = separate_all(audio_path, work_dir)
        error_code = "artifact_upload_failed"
        for stem in STEMS:
            _upload_output(payload["output_upload_urls"][stem], output_paths[stem])
        _write_status(status_url, "completed")
        logger.info("Stem separation completed job_id=%s", job_id)
    except InvalidAudioError:
        try:
            _write_status(status_url, "failed", "invalid_audio")
        except Exception:
            logger.warning("Stem status write failed job_id=%s", job_id)
        logger.warning("Stem audio was rejected job_id=%s", job_id)
    except AudioSourceError:
        try:
            _write_status(status_url, "failed", error_code)
        except Exception:
            logger.warning("Stem status write failed job_id=%s", job_id)
        logger.warning("Stem source rejected job_id=%s", job_id)
    except Exception:
        try:
            _write_status(status_url, "failed", error_code)
        except Exception:
            logger.warning("Stem status write failed job_id=%s", job_id)
        logger.warning("Stem processing failed job_id=%s code=%s", job_id, error_code)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("songmatch-stem-worker")],
)
@modal.fastapi_endpoint(method="POST")
def start_stem_job(
    request: StemWorkerRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, bool]:
    expected = os.getenv("SONGMATCH_WORKER_TOKEN", "")
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")

    process_song.spawn(request.model_dump(mode="json"))
    return {"accepted": True}
