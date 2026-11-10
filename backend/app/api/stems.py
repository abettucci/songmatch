"""Authenticated endpoints for temporary AI stem processing jobs."""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import PurePath
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    STEM_CONTENT_TYPES,
    STEM_UPLOAD_MAX_BYTES,
    StemJobCreateRequest,
    StemJobResponse,
    StemUploadRequest,
    StemUploadResponse,
)
from app.core.config import get_settings
from app.core.security import require_auth
from app.db.database import get_db
from app.db.models import StemJob
from app.services.stem_artifacts import (
    StemArtifactError,
    create_download_url,
    create_output_upload_url,
    create_status_upload_url,
    create_upload_form,
    inspect_upload,
    read_job_status,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/stems", tags=["AI Stem Mixer"])
STEM_NAMES = ("vocals", "drums", "bass", "other", "guitar", "piano")
JOB_TTL = timedelta(hours=24)
UPLOAD_PREFIX = "stem-artifacts/"


def _user_uuid(user_id: str) -> UUID:
    try:
        return UUID(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Not authenticated") from exc


def _modal_endpoint() -> str:
    endpoint = get_settings().modal_stem_endpoint
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".modal.run"):
        raise HTTPException(status_code=503, detail="Stem processing is not configured")
    return endpoint


@router.post("/uploads", response_model=StemUploadResponse)
async def create_stem_upload(
    request: StemUploadRequest,
    user_id: str = Depends(require_auth),
):
    if request.size > STEM_UPLOAD_MAX_BYTES or request.content_type not in STEM_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported audio file")
    try:
        url, fields, object_key = create_upload_form(
            str(_user_uuid(user_id)), request.content_type, PurePath(request.file_name).suffix.casefold()
        )
    except StemArtifactError:
        logger.warning("Stem upload authorization could not be created")
        raise HTTPException(status_code=503, detail="Audio upload is temporarily unavailable")
    return StemUploadResponse(upload_url=url, fields=fields, source_key=object_key)


@router.post("/jobs", response_model=StemJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_stem_job(
    request: StemJobCreateRequest,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    owner_id = _user_uuid(user_id)
    active_result = await db.execute(
        select(StemJob)
        .where(StemJob.user_id == owner_id, StemJob.status.in_(("queued", "processing")))
        .order_by(StemJob.created_at.desc())
        .limit(1)
    )
    active_job = active_result.scalar_one_or_none()
    if active_job is not None:
        if datetime.now(timezone.utc) - active_job.created_at <= timedelta(minutes=20):
            raise HTTPException(status_code=409, detail="Wait for your current stem job to finish")
        try:
            stale_status = read_job_status(active_job.status_key)
        except StemArtifactError:
            stale_status = None
        if stale_status and stale_status["status"] in {"completed", "failed"}:
            active_job.status = stale_status["status"]
            active_job.error_code = stale_status["error_code"] or None
        else:
            active_job.status = "failed"
            active_job.error_code = "worker_timeout"
        await db.flush()

    source_key: Optional[str] = None

    if request.source_type == "upload":
        source_key = request.source_key
        expected_prefix = f"{UPLOAD_PREFIX}{owner_id}/uploads/"
        if not source_key or not source_key.startswith(expected_prefix) or ".." in source_key:
            raise HTTPException(status_code=400, detail="Invalid audio upload")
        try:
            metadata = inspect_upload(source_key)
        except StemArtifactError:
            raise HTTPException(status_code=400, detail="Upload the audio file before processing it")
        if not 1 <= int(metadata.get("ContentLength", 0)) <= STEM_UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Audio file exceeds the size limit")
        if metadata.get("ContentType") not in STEM_CONTENT_TYPES:
            raise HTTPException(status_code=415, detail="Unsupported audio file")

    job_id = uuid4()
    expires_at = datetime.now(timezone.utc) + JOB_TTL
    output_keys = {
        stem: f"stem-artifacts/{owner_id}/jobs/{job_id}/stems/{stem}.mp3"
        for stem in STEM_NAMES
    }
    job = StemJob(
        id=job_id,
        user_id=owner_id,
        source_type=request.source_type,
        source_key=source_key,
        status_key=f"stem-artifacts/{owner_id}/jobs/{job_id}/status.json",
        status="queued",
        output_keys=output_keys,
        expires_at=expires_at,
    )
    db.add(job)
    await db.flush()

    settings = get_settings()
    if not settings.modal_stem_token:
        raise HTTPException(status_code=503, detail="Stem processing is not configured")

    try:
        upload_urls = {stem: create_output_upload_url(key) for stem, key in output_keys.items()}
        worker_payload = {
            "job_id": str(job_id),
            "source_type": request.source_type,
            "spotify_url": request.spotify_url,
            "source_download_url": create_download_url(source_key) if source_key else None,
            "output_upload_urls": upload_urls,
            "status_upload_url": create_status_upload_url(job.status_key),
        }
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                _modal_endpoint(),
                json=worker_payload,
                headers={"Authorization": f"Bearer {settings.modal_stem_token}"},
            )
            response.raise_for_status()
    except (StemArtifactError, httpx.HTTPError, ValueError):
        job.status = "failed"
        job.error_code = "worker_unavailable"
        await db.flush()
        logger.warning("Stem worker dispatch failed job_id=%s", job_id)
        return StemJobResponse(
            id=job.id, source_type=job.source_type, status="failed", error_code="worker_unavailable", expires_at=job.expires_at
        )

    return StemJobResponse(id=job.id, source_type=job.source_type, status=job.status, expires_at=job.expires_at)


@router.get("/jobs/{job_id}", response_model=StemJobResponse)
async def get_stem_job(
    job_id: UUID,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StemJob).where(StemJob.id == job_id, StemJob.user_id == _user_uuid(user_id))
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Stem job not found")
    if job.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Stem job expired")

    try:
        worker_status = read_job_status(job.status_key)
    except StemArtifactError:
        raise HTTPException(status_code=503, detail="Stem job status is temporarily unavailable")
    if job.status not in {"completed", "failed"}:
        if worker_status and worker_status["status"] in {"completed", "failed"}:
            job.status = worker_status["status"]
            job.error_code = worker_status["error_code"] or None
        elif datetime.now(timezone.utc) - job.created_at > timedelta(minutes=20):
            job.status = "failed"
            job.error_code = "worker_timeout"
        elif worker_status:
            job.status = worker_status["status"]
            job.error_code = worker_status["error_code"] or None
        await db.flush()

    stems = None
    if job.status == "completed":
        try:
            stems = {stem: create_download_url(key) for stem, key in job.output_keys.items()}
        except StemArtifactError:
            raise HTTPException(status_code=503, detail="Stem audio is temporarily unavailable")
    return StemJobResponse(
        id=job.id, source_type=job.source_type, status=job.status,
        error_code=job.error_code, expires_at=job.expires_at, stems=stems
    )


