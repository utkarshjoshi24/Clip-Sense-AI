"""
backend/app/tasks/celery_app.py — Celery application factory.
"""

from celery import Celery
from ..config import get_settings

settings = get_settings()

celery_app = Celery(
    "clipsense",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.pipeline"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # Only ack after task completes (safer for retries)
    worker_prefetch_multiplier=1,  # One task at a time per worker (video processing is heavy)
    task_soft_time_limit=3600,     # 1 hour soft limit
    task_time_limit=3900,          # Hard kill after 65 min
)
