"""
backend/app/main.py — FastAPI application factory.
"""

import logging
import logging.config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .middleware.logging import RequestLoggingMiddleware
from .middleware.rate_limit import limiter
from .routers import auth, videos, clips, exports
from .services.storage import ensure_bucket_exists

settings = get_settings()

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ClipSense API",
        description="AI-powered video highlight detection for short-form content creators.",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # ── Rate limiting ────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── CORS ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request logging ──────────────────────────────────────────────────
    app.add_middleware(RequestLoggingMiddleware)

    # ── Routers ──────────────────────────────────────────────────────────
    app.include_router(auth.router)
    app.include_router(videos.router)
    app.include_router(clips.router)
    app.include_router(exports.router)

    # ── Startup/Shutdown ─────────────────────────────────────────────────
    @app.on_event("startup")
    async def on_startup():
        logger.info("ClipSense API starting up (env=%s)", settings.APP_ENV)
        try:
            ensure_bucket_exists()
            logger.info("Storage bucket ready: %s", settings.STORAGE_BUCKET)
        except Exception as e:
            logger.warning("Could not ensure storage bucket exists: %s", e)

    @app.get("/health")
    async def health():
        return {"status": "ok", "env": settings.APP_ENV}

    return app


app = create_app()
