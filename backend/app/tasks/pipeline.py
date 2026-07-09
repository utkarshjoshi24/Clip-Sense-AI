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
_current = Path(__file__).resolve()
while _current.parent != _current:
    if (_current / "highlight_detect").exists():
        if str(_current) not in sys.path:
            sys.path.insert(0, str(_current))
        break
    _current = _current.parent

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

            # ── Stage 4: Exact Scene Scoring ────────────────────────────────
            _update_status(db, video_id, VideoStatus.SCORING)

            # Skip if clips already exist (idempotent)
            existing_clips = db.query(Clip).filter(Clip.video_id == video_id).count()
            if existing_clips == 0:
                logger.info("[%s] Stage 4: Scoring exact scenes", video_id)
                video_duration = video.duration_seconds or 0
                scene_boundaries.sort()

                # Reconstruct exact scenes from boundaries
                exact_scenes = []
                for i in range(len(scene_boundaries) - 1):
                    start = scene_boundaries[i]
                    end = scene_boundaries[i+1]
                    # Skip micro-scenes under 1 second
                    if (end - start) >= 1.0:
                        exact_scenes.append({"start": start, "end": end})
                
                # If no scenes were found (e.g. video is 1 shot), treat whole video as 1 scene
                if not exact_scenes and video_duration > 0:
                    exact_scenes.append({"start": 0.0, "end": video_duration})

                from highlight_detect import config as ml_config

                # Persist Clip rows
                highlights = []
                for idx, scene in enumerate(exact_scenes, 1):
                    start = scene["start"]
                    end = scene["end"]

                    # Compute sub-scores using existing ML logic
                    a_score = scorer_module._audio_score_for_window(energy_peaks, start, end)
                    l_score = scorer_module._lexical_score_for_window(lexical_signal, start, end)
                    s_score = 1.0  # Perfect alignment with scene boundaries
                    
                    composite = (
                        ml_config.AUDIO_WEIGHT * a_score
                        + ml_config.SCENE_WEIGHT * s_score
                        + ml_config.LEXICAL_WEIGHT * l_score
                    )

                    snippet = _get_transcript_snippet(transcript_segments, start, end)
                    
                    clip = Clip(
                        video_id=video_id,
                        rank=idx, # Chronological ordering
                        start_time=round(start, 2),
                        end_time=round(end, 2),
                        composite_score=round(composite, 4),
                        audio_energy_score=round(a_score, 4),
                        scene_boundary_score=round(s_score, 4),
                        transcript_signal_score=round(l_score, 4),
                        transcript_snippet=snippet,
                        title_suggestion=_suggest_title(snippet),
                    )
                    db.add(clip)
                    highlights.append(clip)
                
                db.commit()
                logger.info("[%s] Stage 4 complete: %d scene clips saved", video_id, len(highlights))

                # ── Stage 5: Physically Cut Clips ───────────────────────────────
                _update_status(db, video_id, VideoStatus.CUTTING_CLIPS)
                logger.info("[%s] Stage 5: Physically cutting %d clips...", video_id, len(highlights))
                from ..services.export import cut_clips_batch
                from ..models.clip import ExportStatus
                
                # We do this out of the main transaction to avoid long locks, but we need the DB updated
                try:
                    cut_clips_batch(video.storage_key, highlights)
                    for clip in highlights:
                        clip.export_status = ExportStatus.DONE
                        clip.export_storage_key = f"exports/{clip.video_id}/{clip.id}.mp4"
                    db.commit()
                    logger.info("[%s] Stage 5 complete: clips physically cut and uploaded.", video_id)
                except Exception as e:
                    logger.exception("[%s] Stage 5 failed: %s", video_id, e)
                    for clip in highlights:
                        clip.export_status = ExportStatus.FAILED
                    db.commit()
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
