"""
backend/app/schemas/clip.py — Pydantic schemas for clip endpoints.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel


class ClipResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    rank: int
    start_time: float
    end_time: float
    composite_score: float
    audio_energy_score: float
    scene_boundary_score: float
    transcript_signal_score: float
    title_suggestion: str | None = None
    transcript_snippet: str | None = None
    export_status: str
    export_url: str | None = None  # Presigned URL for exported mp4
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportRequest(BaseModel):
    clip_ids: list[uuid.UUID]
    format: str = "mp4"  # "mp4", "edl", "fcpxml"


class ExportResponse(BaseModel):
    format: str
    urls: list[str] | None = None   # For mp4 format
    content: str | None = None      # For edl/fcpxml format (inline text)
    filename: str | None = None
