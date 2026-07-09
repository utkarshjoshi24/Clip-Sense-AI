"""
backend/app/models/clip.py — Clip ORM model.
"""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from ..database import Base


class ExportStatus(str, enum.Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)

    # Composite score and individual sub-scores — all stored separately
    # so the frontend can show the per-signal breakdown, not just one number
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    audio_energy_score: Mapped[float] = mapped_column(Float, nullable=False)
    scene_boundary_score: Mapped[float] = mapped_column(Float, nullable=False)
    transcript_signal_score: Mapped[float] = mapped_column(Float, nullable=False)

    title_suggestion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transcript_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    export_status: Mapped[ExportStatus] = mapped_column(
        SAEnum(ExportStatus), default=ExportStatus.PENDING, nullable=False
    )
    # S3 key for the trimmed mp4 (populated after export)
    export_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    video: Mapped["Video"] = relationship("Video", back_populates="clips")  # noqa: F821
