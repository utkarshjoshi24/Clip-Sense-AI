"""
backend/app/routers/exports.py — Export endpoints.

POST /exports — export clips as mp4/edl/fcpxml
"""

import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_verified_email
from ..models.clip import Clip, ExportStatus
from ..models.user import User
from ..models.video import Video
from ..schemas.clip import ExportRequest, ExportResponse
from ..services.export import cut_clip_ffmpeg, generate_edl, generate_fcpxml

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("/", response_model=ExportResponse)
async def export_clips(
    body: ExportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_verified_email),
    db: AsyncSession = Depends(get_db),
):
    if not body.clip_ids:
        raise HTTPException(status_code=400, detail="No clips selected")

    if body.format not in ("mp4", "edl", "fcpxml"):
        raise HTTPException(status_code=400, detail="Format must be mp4, edl, or fcpxml")

    # Load clips and verify ownership
    result = await db.execute(
        select(Clip).where(Clip.id.in_(body.clip_ids))
    )
    clips = result.scalars().all()

    if not clips:
        raise HTTPException(status_code=404, detail="No clips found")

    # Verify all clips belong to videos owned by current user
    video_ids = {clip.video_id for clip in clips}
    for vid_id in video_ids:
        v_result = await db.execute(
            select(Video).where(Video.id == vid_id, Video.user_id == current_user.id)
        )
        if not v_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied to one or more clips")

    # ── EDL ──
    if body.format == "edl":
        video_result = await db.execute(
            select(Video).where(Video.id == list(video_ids)[0])
        )
        video = video_result.scalar_one()
        sorted_clips = sorted(clips, key=lambda c: c.start_time)
        edl_content = generate_edl(sorted_clips, video.filename)
        return ExportResponse(
            format="edl",
            content=edl_content,
            filename=f"{video.filename.rsplit('.', 1)[0]}_highlights.edl",
        )

    # ── FCPXML ──
    if body.format == "fcpxml":
        video_result = await db.execute(
            select(Video).where(Video.id == list(video_ids)[0])
        )
        video = video_result.scalar_one()
        sorted_clips = sorted(clips, key=lambda c: c.start_time)
        xml_content = generate_fcpxml(sorted_clips, video.filename)
        return ExportResponse(
            format="fcpxml",
            content=xml_content,
            filename=f"{video.filename.rsplit('.', 1)[0]}_highlights.fcpxml",
        )

    # ── MP4: cut each clip server-side ──
    urls = []
    for clip in clips:
        video_result = await db.execute(select(Video).where(Video.id == clip.video_id))
        video = video_result.scalar_one()

        if clip.export_storage_key:
            # Already exported — return existing presigned URL
            from ..services.storage import generate_presigned_url
            urls.append(generate_presigned_url(clip.export_storage_key))
        else:
            # Cut and upload (synchronous for now — move to Celery for large batches)
            try:
                url = cut_clip_ffmpeg(video.storage_key, clip)
                clip.export_status = ExportStatus.DONE
                clip.export_storage_key = f"exports/{clip.video_id}/{clip.id}.mp4"
                urls.append(url)
            except Exception as e:
                clip.export_status = ExportStatus.FAILED
                raise HTTPException(status_code=500, detail=f"Export failed: {str(e)[:200]}")

    await db.commit()
    return ExportResponse(format="mp4", urls=urls)
