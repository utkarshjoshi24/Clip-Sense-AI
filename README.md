# ClipSense

> AI-powered video highlight detection web application — wraps a validated Phase 0 ML pipeline in a production-grade FastAPI + React web app.

## Architecture

```
frontend/  (React + Tailwind + Vite)
backend/   (FastAPI + Celery + SQLAlchemy)
highlight_detect/  (Phase 0 ML module — imported, NOT modified)
infra/     (docker-compose, Dockerfiles, .env.example)
```

## Quick Start (Docker)

```bash
# 1. Copy and configure environment
cp infra/.env.example infra/.env
# → edit infra/.env: set JWT_SECRET_KEY, Google OAuth keys, etc.

# 2. Launch the full stack
cd infra && docker compose up --build

# Services:
#   API:        http://localhost:8000  (Swagger: http://localhost:8000/docs)
#   Frontend:   http://localhost:5173
#   MinIO UI:   http://localhost:9001  (user: minioadmin / minioadmin)
```

## Local Dev (without Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Worker (separate terminal)
celery -A app.tasks.celery_app:celery_app worker --loglevel=info

# Frontend (separate terminal)
cd frontend
npm install && npm run dev
```

## Environment Variables

See [infra/.env.example](infra/.env.example) for all configurable variables.

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis URL for Celery broker |
| `JWT_SECRET_KEY` | Secret key for JWT signing (generate: `openssl rand -hex 32`) |
| `STORAGE_ENDPOINT` | MinIO/S3/R2 endpoint URL |
| `STORAGE_ACCESS_KEY` | Storage access key |
| `STORAGE_SECRET_KEY` | Storage secret key |
| `EMAIL_MOCK` | Set `true` in dev to print emails to console |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (optional) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret (optional) |

## How highlight_detect Plugs Into the Web Layer

The Celery worker imports the Phase 0 ML functions **directly**:

```python
# backend/app/tasks/pipeline.py
from highlight_detect.audio_energy import extract_audio, analyze_energy
from highlight_detect.scene_detect import detect_scenes_full
from highlight_detect.transcribe import transcribe_audio, compute_lexical_signal
from highlight_detect import scorer as scorer_module
```

The pipeline task:
1. Downloads the uploaded video from S3/MinIO to a temp path
2. Calls each ML function in sequence, updating `Video.status` after each stage
3. Persists `SceneBoundary` rows (raw scene detection output) and `Clip` rows (scored highlights) to PostgreSQL
4. Cleans up temp files on completion

The ML logic is **never modified** — the web layer only wraps and orchestrates it.

## Plan Limits (enforced server-side)

| Plan | Videos/month | Max duration | Max file size |
|------|-------------|--------------|---------------|
| Free | 3 | 15 min | 500 MB |
| Pro  | Unlimited | 2 hours | 2 GB |

## Running Tests

```bash
cd backend
pytest tests/ -v
```

## Export Formats

- **MP4** — server-side ffmpeg trim, uploaded to storage, returns presigned download URLs
- **EDL** — CMX 3600 format, importable into DaVinci Resolve and Premiere Pro
- **FCPXML** — Final Cut Pro XML, importable into FCP and Premiere Pro
