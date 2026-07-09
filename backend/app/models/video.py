"""
backend/app/models/video.py — Video and SceneBoundary ORM models.
"""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from ..database import Base


class VideoStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    EXTRACTING_AUDIO = "extracting_audio"
    DETECTING_SCENES = "detecting_scenes"
    TRANSCRIBING = "transcribing"
    SCORING = "scoring"
    DONE = "done"
    FAILED = "failed"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[VideoStatus] = mapped_column(
        SAEnum(VideoStatus), default=VideoStatus.UPLOADED, nullable=False, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="videos")  # noqa: F821
    clips: Mapped[list["Clip"]] = relationship(  # noqa: F821
        "Clip", back_populates="video", cascade="all, delete-orphan"
    )
    scene_boundaries: Mapped[list["SceneBoundary"]] = relationship(
        "SceneBoundary", back_populates="video", cascade="all, delete-orphan"
    )


class SceneBoundary(Base):
    """Stores the raw high-sensitivity scene detection output as a reference.

    These are stored separately from the composite score — they inform the
    scene_boundary_score sub-signal in Clip but are also useful for the
    --scene-cut export mode.
    """
    __tablename__ = "scene_boundaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)

    video: Mapped["Video"] = relationship("Video", back_populates="scene_boundaries")
