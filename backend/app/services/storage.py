"""
backend/app/services/storage.py — S3-compatible object storage via boto3.

Works with MinIO (local dev), AWS S3, and Cloudflare R2 in production.
Never stores files on local disk in production — all video data lives in object storage.
All client-facing URLs are presigned and time-limited.
"""

import hashlib
import io
import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _get_client(presigned: bool = False):
    endpoint_url = settings.STORAGE_ENDPOINT
    if presigned and settings.APP_ENV == "development":
        endpoint_url = endpoint_url.replace("http://minio:9000", "http://localhost:9000")

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        region_name=settings.STORAGE_REGION,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket_exists() -> None:
    """Create the storage bucket if it doesn't exist (startup check)."""
    client = _get_client()
    try:
        client.head_bucket(Bucket=settings.STORAGE_BUCKET)
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            client.create_bucket(Bucket=settings.STORAGE_BUCKET)
            logger.info("Created storage bucket: %s", settings.STORAGE_BUCKET)
        else:
            raise
    
    # Always ensure CORS is configured for browser playback
    cors_configuration = {
        'CORSRules': [{
            'AllowedHeaders': ['*'],
            'AllowedMethods': ['GET', 'PUT', 'POST', 'HEAD', 'DELETE'],
            'AllowedOrigins': ['*'],
            'ExposeHeaders': ['ETag', 'Accept-Ranges', 'Content-Encoding', 'Content-Length', 'Content-Range'],
            'MaxAgeSeconds': 3600
        }]
    }
    client.put_bucket_cors(Bucket=settings.STORAGE_BUCKET, CORSConfiguration=cors_configuration)


def upload_fileobj(file_obj: io.IOBase, key: str, content_type: str = "video/mp4") -> str:
    """Upload a file-like object to storage. Returns the storage key."""
    client = _get_client()
    client.upload_fileobj(
        file_obj,
        settings.STORAGE_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    logger.info("Uploaded file to storage: %s", key)
    return key


def generate_presigned_url(key: str, expiry_seconds: int = 3600, download_filename: str | None = None) -> str:
    """Generate a presigned URL for client download (time-limited, no public bucket)."""
    client = _get_client(presigned=True)
    params = {"Bucket": settings.STORAGE_BUCKET, "Key": key}
    if download_filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'

    url = client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expiry_seconds,
    )
    return url


def generate_presigned_upload_url(key: str, expiry_seconds: int = 600) -> str:
    """Generate a presigned PUT URL for direct-to-storage uploads."""
    client = _get_client(presigned=True)
    url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.STORAGE_BUCKET, "Key": key},
        ExpiresIn=expiry_seconds,
    )
    return url


@contextmanager
def download_to_temp(key: str, suffix: str = ".mp4"):
    """Download a storage object to a temp file. Yields the local Path.
    
    Cleans up the temp file on exit. Use as a context manager.
    """
    tmp_dir = Path(settings.WORKER_TMP_DIR)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    client = _get_client()
    with tempfile.NamedTemporaryFile(
        dir=str(tmp_dir), suffix=suffix, delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        logger.info("Downloading %s → %s", key, tmp_path)
        client.download_file(settings.STORAGE_BUCKET, key, str(tmp_path))
        yield tmp_path
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
            logger.info("Cleaned up temp file: %s", tmp_path)


def delete_object(key: str) -> None:
    """Delete an object from storage."""
    client = _get_client()
    client.delete_object(Bucket=settings.STORAGE_BUCKET, Key=key)
    logger.info("Deleted storage object: %s", key)


def compute_file_hash(file_path: Path, chunk_size_mb: int = 10) -> str:
    """Compute SHA-256 hash of first N MB of a file for cache keying.
    
    Reads only the first chunk to avoid hashing multi-GB files.
    """
    h = hashlib.sha256()
    chunk_size = chunk_size_mb * 1024 * 1024
    with open(file_path, "rb") as f:
        data = f.read(chunk_size)
        h.update(data)
    return h.hexdigest()[:16]
