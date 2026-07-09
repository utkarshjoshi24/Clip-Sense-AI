"""
backend/app/routers/videos.py — Video upload, listing, and detail endpoints.

POST /videos/upload — multipart upload with magic-byte validation + plan limits
GET  /videos/       — list user's videos
GET  /videos/{id}   — video detail with presigned URL
DELETE /videos/{id} — delete video and associated data
"""

import hashlib
import io
import logging
import subprocess
import uuid
from pathlib import Path

import magic
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..dependencies import get_current_user, require_verified_email
from ..middleware.rate_limit import limiter
from ..models.user import User, UserRole
from ..models.video import Video, VideoStatus
from ..schemas.video import VideoListResponse, VideoResponse
from ..services.storage import delete_object, generate_presigned_url, upload_fileobj
from ..tasks.pipeline import process_video

settings = get_settings()
router = APIRouter(prefix="/videos", tags=["videos"])
logger = logging.getLogger(__name__)

# Allowed video MIME types (verified via magic bytes, not extension)
ALLOWED_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/webm",
}


def _validate_magic_bytes(data: bytes) -> str:
    """Inspect file content to determine MIME type. Raises if not a valid video."""
    mime = magic.from_buffer(data, mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{mime}'. Allowed: mp4, mov, avi, mkv, webm",
        )
    return mime


def _get_plan_limits(user: User) -> tuple[int, int]:
    """Returns (max_file_bytes, max_duration_sec) for the user's plan."""
    if user.role == UserRole.PRO or user.role.value == "admin":
        return settings.PRO_MAX_FILE_SIZE_BYTES, settings.PRO_MAX_VIDEO_DURATION_SEC
    return settings.FREE_MAX_FILE_SIZE_BYTES, settings.FREE_MAX_VIDEO_DURATION_SEC


async def _check_monthly_limit(db: AsyncSession, user: User) -> None:
    """Enforce free plan upload count limit."""
    if user.role != UserRole.FREE:
        return

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(Video.id)).where(
            Video.user_id == user.id,
            Video.created_at >= first_of_month,
        )
    )
    count = result.scalar_one()
    if count >= settings.FREE_MAX_VIDEOS_PER_MONTH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Free plan limit: {settings.FREE_MAX_VIDEOS_PER_MONTH} videos/month. Upgrade to Pro for unlimited uploads.",
        )


def _get_video_duration_ffprobe(file_path: str) -> float | None:
    """Get video duration using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def _build_video_response(video: Video, with_url: bool = False) -> VideoResponse:
    resp = VideoResponse.model_validate(video)
    if with_url and video.status == VideoStatus.DONE:
        resp.preview_url = generate_presigned_url(video.storage_key, expiry_seconds=3600)
    return resp


@router.post("/upload", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_verified_email),
    db: AsyncSession = Depends(get_db),
):
    max_bytes, max_duration = _get_plan_limits(current_user)

    # 1. Check monthly limit (free plan)
    await _check_monthly_limit(db, current_user)

    # 2. Read file into memory for magic-byte check
    # Read first 2KB for magic bytes check, then read the rest
    header = await file.read(2048)
    mime_type = _validate_magic_bytes(header)

    # 3. Check file size limit
    rest = await file.read()
    total_bytes = len(header) + len(rest)
    if total_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Your plan allows up to {max_bytes // (1024*1024)}MB.",
        )

    file_data = header + rest

    # 4. Save temporarily to check duration via ffprobe
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(file_data)
        tmp_path = tmp.name

    try:
        duration = _get_video_duration_ffprobe(tmp_path)
        if duration and duration > max_duration:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Video too long. Your plan allows up to {max_duration // 60} minutes.",
            )
    finally:
        os.unlink(tmp_path)

    # 5. Upload to object storage
    safe_name = Path(file.filename).name  # strip path traversal
    storage_key = f"videos/{current_user.id}/{uuid.uuid4()}/{safe_name}"

    upload_fileobj(io.BytesIO(file_data), storage_key, content_type=mime_type)

    # 6. Create Video DB record
    video = Video(
        user_id=current_user.id,
        filename=safe_name,
        storage_key=storage_key,
        duration_seconds=duration,
        status=VideoStatus.UPLOADED,
    )
    db.add(video)
    await db.flush()
    video_id = str(video.id)

    # 7. Enqueue Celery processing task
    process_video.apply_async(args=[video_id], task_id=f"pipeline-{video_id}")
    logger.info("Enqueued pipeline task for video %s", video_id)

    return _build_video_response(video)


@router.get("/", response_model=VideoListResponse)
async def list_videos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    result = await db.execute(
        select(Video)
        .where(Video.user_id == current_user.id)
        .order_by(Video.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    videos = result.scalars().all()

    count_result = await db.execute(
        select(func.count(Video.id)).where(Video.user_id == current_user.id)
    )
    total = count_result.scalar_one()

    return VideoListResponse(
        videos=[_build_video_response(v) for v in videos],
        total=total,
    )


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return _build_video_response(video, with_url=True)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Delete from storage
    try:
        delete_object(video.storage_key)
    except Exception as e:
        logger.warning("Could not delete storage object %s: %s", video.storage_key, e)

    await db.delete(video)
