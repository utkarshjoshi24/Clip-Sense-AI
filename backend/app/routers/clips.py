"""
backend/app/routers/clips.py — Clip listing for a video.

GET /videos/{video_id}/clips — list all clips for a video
GET /videos/{video_id}/clips/{clip_id} — single clip detail
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models.clip import Clip
from ..models.video import Video
from ..models.user import User
from ..schemas.clip import ClipResponse
from ..services.storage import generate_presigned_url

router = APIRouter(tags=["clips"])


def _clip_response(clip: Clip) -> ClipResponse:
    resp = ClipResponse.model_validate(clip)
    if clip.export_storage_key:
        resp.export_url = generate_presigned_url(clip.export_storage_key)
    return resp


@router.get("/videos/{video_id}/clips", response_model=list[ClipResponse])
async def list_clips(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify video ownership
    v_result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    if not v_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Video not found")

    result = await db.execute(
        select(Clip).where(Clip.video_id == video_id).order_by(Clip.rank)
    )
    return [_clip_response(c) for c in result.scalars().all()]


@router.get("/videos/{video_id}/clips/{clip_id}", response_model=ClipResponse)
async def get_clip(
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    v_result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    if not v_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Video not found")

    result = await db.execute(
        select(Clip).where(Clip.id == clip_id, Clip.video_id == video_id)
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    return _clip_response(clip)
