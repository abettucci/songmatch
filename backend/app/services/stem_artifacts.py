"""Private, short-lived S3 artifacts used by the AI Stem Mixer."""

import json
from typing import Any, Optional
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.api.schemas import STEM_UPLOAD_MAX_BYTES
from app.core.config import get_settings


class StemArtifactError(Exception):
    """Raised when temporary artifact storage is unavailable."""


def _client():
    settings = get_settings()
    return boto3.client("s3", region_name=settings.aws_region)


def _bucket() -> str:
    bucket = get_settings().stem_artifacts_bucket
    if not bucket:
        raise StemArtifactError("Artifact storage is not configured")
    return bucket


def create_upload_form(user_id: str, content_type: str, extension: str) -> tuple[str, dict[str, str], str]:
    object_key = f"stem-artifacts/{user_id}/uploads/{uuid4()}/source{extension}"
    try:
        post = _client().generate_presigned_post(
            Bucket=_bucket(),
            Key=object_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, STEM_UPLOAD_MAX_BYTES],
            ],
            ExpiresIn=600,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StemArtifactError("Could not create upload authorization") from exc
    return post["url"], post["fields"], object_key


def inspect_upload(object_key: str) -> dict[str, Any]:
    try:
        return _client().head_object(Bucket=_bucket(), Key=object_key)
    except (BotoCoreError, ClientError) as exc:
        raise StemArtifactError("Uploaded audio is unavailable") from exc


def create_download_url(object_key: str) -> str:
    try:
        return _client().generate_presigned_url(
            "get_object", Params={"Bucket": _bucket(), "Key": object_key}, ExpiresIn=3600
        )
    except (BotoCoreError, ClientError) as exc:
        raise StemArtifactError("Could not create audio access URL") from exc


def create_output_upload_url(object_key: str) -> str:
    try:
        return _client().generate_presigned_url(
            "put_object",
            Params={"Bucket": _bucket(), "Key": object_key, "ContentType": "audio/mpeg"},
            ExpiresIn=3600,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StemArtifactError("Could not create output upload authorization") from exc


def create_status_upload_url(object_key: str) -> str:
    try:
        return _client().generate_presigned_url(
            "put_object",
            Params={"Bucket": _bucket(), "Key": object_key, "ContentType": "application/json"},
            ExpiresIn=3600,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StemArtifactError("Could not create job status authorization") from exc


def read_job_status(object_key: str) -> Optional[dict[str, str]]:
    try:
        response = _client().get_object(Bucket=_bucket(), Key=object_key)
        document = json.loads(response["Body"].read(4096).decode("utf-8"))
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404", "NotFound"}:
            return None
        raise StemArtifactError("Could not read job status") from exc
    except (BotoCoreError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StemArtifactError("Could not read job status") from exc
    if not isinstance(document, dict):
        raise StemArtifactError("Invalid job status")
    status_value = document.get("status")
    error_code = document.get("error_code")
    if status_value not in {"processing", "completed", "failed"}:
        raise StemArtifactError("Invalid job status")
    if error_code is not None and error_code not in {
        "source_unavailable", "invalid_audio", "separation_failed", "artifact_upload_failed"
    }:
        raise StemArtifactError("Invalid job status")
    return {"status": status_value, "error_code": error_code or ""}
