"""
backend/app/schemas/video.py — Pydantic schemas for video endpoints.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel


class VideoResponse(BaseModel):
    id: uuid.UUID
    filename: str
    duration_seconds: float | None
    status: str
    error_message: str | None = None
    created_at: datetime
    preview_url: str | None = None  # Presigned URL, added at response time

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    videos: list[VideoResponse]
    total: int


class SceneBoundaryResponse(BaseModel):
    id: uuid.UUID
    timestamp: float

    model_config = {"from_attributes": True}
