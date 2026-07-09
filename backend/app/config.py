"""
backend/app/config.py — Application settings via Pydantic BaseSettings.

All configuration is read from environment variables.
Never hardcode secrets here — use the .env file (or real env in production).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────────
    APP_NAME: str = "ClipSense"
    APP_ENV: Literal["development", "production", "test"] = "development"
    DEBUG: bool = False

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://clipsense:clipsense@localhost:5432/clipsense"

    # ── Redis / Celery ─────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── JWT ────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Object Storage (MinIO / S3 / R2) ──────────────────────────────────
    STORAGE_ENDPOINT: str = "http://localhost:9000"
    STORAGE_ACCESS_KEY: str = "minioadmin"
    STORAGE_SECRET_KEY: str = "minioadmin"
    STORAGE_BUCKET: str = "clipsense"
    STORAGE_REGION: str = "us-east-1"
    STORAGE_USE_SSL: bool = False

    # ── Email ──────────────────────────────────────────────────────────────
    EMAIL_MOCK: bool = True          # In dev, print emails to console
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@clipsense.app"
    FRONTEND_URL: str = "http://localhost:5173"

    # ── Google OAuth ───────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""       # Add after creating GCP project
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # ── CORS ───────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # ── Plan Limits ────────────────────────────────────────────────────────
    FREE_MAX_VIDEOS_PER_MONTH: int = 3
    FREE_MAX_VIDEO_DURATION_SEC: int = 900     # 15 min
    FREE_MAX_FILE_SIZE_BYTES: int = 500 * 1024 * 1024   # 500 MB

    PRO_MAX_VIDEO_DURATION_SEC: int = 7200     # 2 hr
    PRO_MAX_FILE_SIZE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GB

    # ── Processing ────────────────────────────────────────────────────────
    # Temp directory inside the worker container for downloaded videos
    WORKER_TMP_DIR: str = "/tmp/clipsense"

    # Default scoring parameters (passed to highlight_detect)
    DEFAULT_MIN_CLIP_LENGTH: int = 60
    DEFAULT_MAX_CLIP_LENGTH: int = 600
    DEFAULT_TOP_N: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
