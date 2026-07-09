"""
backend/app/tasks/pipeline.py — Celery task: process_video

Orchestrates the 4-stage highlight-detection pipeline by calling the
existing /highlight_detect module functions as-is. Does NOT reimplement
any ML logic — it only wraps, marshals results into the DB, and manages
progress state.

Pipeline stages:
  1. extracting_audio  → audio_energy.extract_audio + analyze_energy
  2. detecting_scenes  → scene_detect.detect_scenes_full + persist SceneBoundary rows
  3. transcribing      → transcribe.transcribe_audio + compute_lexical_signal
  4. scoring           → scorer.score_windows + deduplicate_windows + persist Clip rows

The task is idempotent: it checks existing DB rows before running each stage
so a crashed/retried task won't corrupt state.
"""

import logging
import os
import sys
from pathlib import Path

from celery import Task
from sqlalchemy import select
from sqlalchemy.orm import Session

from .celery_app import celery_app
from ..config import get_settings
from ..database import AsyncSessionLocal
from ..models.clip import Clip
from ..models.video import Video, VideoStatus, SceneBoundary
from ..services.storage import download_to_temp, compute_file_hash

# ── Import the validated ML pipeline (DO NOT MODIFY these functions) ─────────
# Add project root to path so highlight_detect is importable from the worker
_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from highlight_detect.audio_energy import extract_audio, analyze_energy
from highlight_detect.scene_detect import detect_scenes_full
from highlight_detect.transcribe import transcribe_audio, compute_lexical_signal
from highlight_detect import scorer as scorer_module

settings = get_settings()
logger = logging.getLogger(__name__)


def _get_sync_db():
    """Create a synchronous SQLAlchemy session for Celery (non-async context)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _update_status(db: Session, video_id: str, status: VideoStatus, error: str | None = None):
    video = db.query(Video).filter(Video.id == video_id).first()
    if video:
        video.status = status
        if error:
            video.error_message = error
        db.commit()


def _get_transcript_snippet(
    transcript_segments: list[dict],
    start: float,
    end: float,
    max_chars: int = 300,
) -> str:
    texts = []
    for seg in transcript_segments:
        if seg["end"] >= start and seg["start"] <= end:
            texts.append(seg["text"])
    full = " ".join(texts).strip()
    return full[:max_chars] + ("..." if len(full) > max_chars else "")


def _suggest_title(transcript_snippet: str) -> str:
    """Generate a simple title suggestion from the first sentence of the transcript."""
    if not transcript_snippet:
        return "Highlight Clip"
    # Take first sentence or first 60 chars
    sentence_end = transcript_snippet.find(".")
    if 0 < sentence_end <= 60:
        return transcript_snippet[:sentence_end + 1].strip()
    return transcript_snippet[:60].strip() + ("..." if len(transcript_snippet) > 60 else "")


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="clipsense.process_video",
)
def process_video(self: Task, video_id: str) -> dict:
    """Process a video through the full highlight-detection pipeline.

    Args:
        video_id: UUID string of the Video record.

    Returns:
        Dict with summary of results.
    """
    logger.info("Starting pipeline for video %s", video_id)
    db = _get_sync_db()

    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found in database")

        # If already done, skip (idempotency)
        if video.status == VideoStatus.DONE:
            logger.info("Video %s already processed, skipping", video_id)
            return {"status": "already_done", "video_id": video_id}

        # Reset error if retrying
        video.error_message = None

        # ── Download video from storage ──────────────────────────────────
        with download_to_temp(video.storage_key, suffix=".mp4") as video_path:
            cache_key = compute_file_hash(video_path)
            cache_dir = Path(settings.WORKER_TMP_DIR) / "cache" / video_id
            cache_dir.mkdir(parents=True, exist_ok=True)

            # ── Stage 1: Audio Extraction + Energy Analysis ───────────────
            existing_clips = db.query(Clip).filter(Clip.video_id == video_id).count()
            if video.status in (VideoStatus.UPLOADED, VideoStatus.EXTRACTING_AUDIO) or existing_clips == 0:
                _update_status(db, video_id, VideoStatus.EXTRACTING_AUDIO)
                logger.info("[%s] Stage 1: Extracting audio + energy analysis", video_id)

                audio_path = extract_audio(str(video_path), cache_dir)
                energy_peaks = analyze_energy(str(audio_path), cache_key, cache_dir)
                logger.info("[%s] Stage 1 complete: %d energy peaks", video_id, len(energy_peaks))
            else:
                # Resume from cache
                audio_path = cache_dir / "audio.wav"
                energy_peaks = analyze_energy(str(audio_path), cache_key, cache_dir)

            # ── Stage 2: Scene Detection ──────────────────────────────────
            _update_status(db, video_id, VideoStatus.DETECTING_SCENES)

            existing_boundaries = db.query(SceneBoundary).filter(
                SceneBoundary.video_id == video_id
            ).count()

            if existing_boundaries == 0:
                logger.info("[%s] Stage 2: Scene detection", video_id)
                scenes = detect_scenes_full(str(video_path), cache_key, cache_dir)

                # Persist SceneBoundary rows
                for scene in scenes:
                    sb = SceneBoundary(
                        video_id=video_id,
                        timestamp=scene["start"],
                    )
                    db.add(sb)
                # Also add the last scene's end as a boundary
                if scenes:
                    db.add(SceneBoundary(video_id=video_id, timestamp=scenes[-1]["end"]))
                db.commit()
                logger.info("[%s] Stage 2 complete: %d scene boundaries", video_id, len(scenes))
            else:
                logger.info("[%s] Stage 2: Scene boundaries already in DB, loading", video_id)
                scenes = [
                    {"start": sb.timestamp, "end": 0, "scene_num": i, "duration": 0}
                    for i, sb in enumerate(
                        db.query(SceneBoundary).filter(
                            SceneBoundary.video_id == video_id
                        ).order_by(SceneBoundary.timestamp).all()
                    )
                ]

            scene_boundaries = [sb.timestamp for sb in
                db.query(SceneBoundary).filter(SceneBoundary.video_id == video_id).all()
            ]

            # ── Stage 3: Transcription + Lexical Signal ───────────────────
            _update_status(db, video_id, VideoStatus.TRANSCRIBING)
            logger.info("[%s] Stage 3: Whisper transcription", video_id)

            transcript_segments = transcribe_audio(str(audio_path), cache_key, cache_dir)
            lexical_signal = compute_lexical_signal(transcript_segments)
            logger.info("[%s] Stage 3 complete: %d segments", video_id, len(transcript_segments))

            # ── Stage 4: Composite Scoring ────────────────────────────────
            _update_status(db, video_id, VideoStatus.SCORING)

            # Skip if clips already exist (idempotent)
            existing_clips = db.query(Clip).filter(Clip.video_id == video_id).count()
            if existing_clips == 0:
                logger.info("[%s] Stage 4: Scoring windows", video_id)

                video_duration = video.duration_seconds or 0
                min_clip = settings.DEFAULT_MIN_CLIP_LENGTH
                max_clip = min(settings.DEFAULT_MAX_CLIP_LENGTH, int(video_duration))

                # Call the existing scorer functions as-is
                scored = scorer_module.score_windows(
                    energy_peaks=energy_peaks,
                    scene_boundaries=scene_boundaries,
                    lexical_signal=lexical_signal,
                    video_duration=video_duration,
                    min_clip_length=min_clip,
                    max_clip_length=max_clip,
                )
                highlights = scorer_module.deduplicate_windows(
                    scored, top_n=settings.DEFAULT_TOP_N
                )

                # Persist Clip rows
                for rank, h in enumerate(highlights, 1):
                    snippet = _get_transcript_snippet(
                        transcript_segments, h["start"], h["end"]
                    )
                    clip = Clip(
                        video_id=video_id,
                        rank=rank,
                        start_time=h["start"],
                        end_time=h["end"],
                        composite_score=h["score"],
                        audio_energy_score=h["audio_score"],
                        scene_boundary_score=h["scene_score"],
                        transcript_signal_score=h["lexical_score"],
                        transcript_snippet=snippet,
                        title_suggestion=_suggest_title(snippet),
                    )
                    db.add(clip)
                db.commit()
                logger.info("[%s] Stage 4 complete: %d clips saved", video_id, len(highlights))
            else:
                logger.info("[%s] Stage 4: Clips already in DB, skipping", video_id)

            # ── Done ──────────────────────────────────────────────────────
            _update_status(db, video_id, VideoStatus.DONE)
            logger.info("[%s] Pipeline complete", video_id)

            return {
                "status": "done",
                "video_id": video_id,
                "clips": db.query(Clip).filter(Clip.video_id == video_id).count(),
                "scene_boundaries": len(scene_boundaries),
            }

    except Exception as exc:
        logger.error("[%s] Pipeline failed: %s", video_id, exc, exc_info=True)
        _update_status(db, video_id, VideoStatus.FAILED, error=str(exc))

        # Retry with backoff for transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
        raise

    finally:
        db.close()
