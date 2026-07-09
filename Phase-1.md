# Phase 1 — Web App MVP (Antigravity Prompt)

Tailored to your Phase 0 results: scene detection runs at high sensitivity to catch subtle camera shifts/movements and is stored as a separate boundary-reference file (not a ranked signal itself), and the three scoring signals (audio energy, scene-boundary proximity, transcript/hook-word density) are weighted roughly equally. This prompt tells Antigravity to reuse your Phase 0 modules directly rather than rebuild the ML logic from scratch — don't let it regenerate audio_energy.py, scene_detect.py, transcribe.py, or scorer.py from nothing; it should import and wrap what you already validated.

---

## Before you paste this in

Have your Phase 0 project folder accessible in the same workspace (or copy `/highlight_detect` into the new project root first). Tell Antigravity explicitly to treat that folder as ground truth — this avoids it "helpfully" rewriting your already-tuned scoring logic.

---

## Antigravity prompt

```
You are building "ClipSense" — a production-grade web application that wraps an
already-validated highlight-detection ML pipeline for short-form content creators.

CRITICAL: I have an existing, validated Python module at /highlight_detect containing:
- audio_energy.py — computes audio energy peaks
- scene_detect.py — runs high-sensitivity scene detection (tuned to catch subtle
  camera shifts and movements), outputs scene-boundary timestamps to a separate
  reference file rather than as a ranked/scored signal
- transcribe.py — local Whisper transcription with hook-word/lexical signal detection
- scorer.py — composite scoring using roughly equal weighting (~0.33 each) across
  audio energy, proximity to a scene boundary, and transcript signal, merging
  overlapping windows and returning top-N ranked candidate clips
- config.py — tunable weights and thresholds

DO NOT rewrite or regenerate this ML logic. Import and wrap these existing, tested
functions as-is. Your job is to build the web application, database, auth, and API
layer AROUND this validated pipeline — treat /highlight_detect as a black-box
dependency that already works correctly. If you need to modify it, ask me first
and explain why, rather than silently rewriting it.

CORE FUNCTIONALITY:
1. User uploads a video file (mp4/mov, up to 2GB) via a React frontend.
2. Backend (FastAPI) queues the video for async processing via Celery + Redis.
3. A Celery task calls the existing /highlight_detect pipeline functions in sequence
   (audio energy -> scene detection -> transcription -> scoring), persists progress
   to the Video.status field after each stage so the frontend can poll for progress,
   and stores the final ranked clip list in the database.
4. Frontend displays candidate clips as a scrollable list with inline video preview
   (seek to timestamp in an HTML5 video player), confidence/composite score, and
   the transcript snippet for that window.
5. User selects clips to export:
   - Individual trimmed MP4s (server-side ffmpeg cut)
   - An EDL or FCPXML file containing markers for all selected clips, importable
     into DaVinci Resolve or Premiere Pro

AUTHENTICATION & AUTHORIZATION:
- Email/password signup with email verification (use a placeholder/mock email
  service in dev, real transactional service in prod config).
- JWT access tokens (15 min expiry) + refresh tokens stored as httpOnly, secure,
  sameSite cookies, with refresh token rotation.
- Google OAuth as a secondary login method.
- Roles: "free" (3 videos/month, max 15 min video length) and "pro" (unlimited,
  max 2 hour video length). Enforce limits server-side at the API layer, not just
  the frontend.
- Password reset flow (expiring, single-use tokens).
- Every authenticated endpoint validates the JWT and checks role-based permissions
  server-side, never trusting the frontend's assumed role.

SECURITY REQUIREMENTS (implement all of these, not optional):
- Store uploaded videos in S3-compatible object storage (MinIO for local dev,
  configurable for AWS S3 / Cloudflare R2 in production) — never on local disk
  in production config.
- Signed, time-expiring URLs for any client access to stored files — no public
  buckets, ever.
- Validate file type via actual content/magic-byte inspection before accepting
  an upload, not just the file extension.
- Enforce file size and duration limits server-side, matched to the user's plan tier.
- Rate-limit all API endpoints, with stricter limits on auth endpoints specifically.
- All secrets (DB credentials, JWT signing key, storage keys) come from environment
  variables only. Provide a .env.example.
- Hash passwords with argon2 or bcrypt.
- Use SQLAlchemy with parameterized queries throughout — no raw string-interpolated SQL.
- CORS restricted to the actual frontend origin in production config, not wildcard.
- Structured request/error logging, ready to plug into Sentry later.

DATA MODELS (PostgreSQL via SQLAlchemy):
- User: id, email, hashed_password, role, email_verified, created_at, oauth_provider
- Video: id, user_id, filename, storage_key, duration_seconds, status
  (uploaded/extracting_audio/detecting_scenes/transcribing/scoring/done/failed),
  created_at
- Clip: id, video_id, start_time, end_time, composite_score, audio_energy_score,
  scene_boundary_score, transcript_signal_score, title_suggestion, transcript_snippet,
  export_status
- SceneBoundary: id, video_id, timestamp — stores the raw high-sensitivity scene
  detection output separately, matching how /highlight_detect already structures it
- Subscription: id, user_id, plan, status, current_period_end (structure now, Stripe/
  Razorpay integration can be stubbed for a later pass)

PROCESSING PIPELINE (Celery task):
- Idempotent and resumable — a crashed worker mid-job should be retryable without
  corrupting state.
- Update Video.status after each pipeline stage completes so the frontend can show
  real progress, not a generic spinner.
- Reuse the caching approach from /highlight_detect (keyed by video content hash) so
  re-processing doesn't re-run Whisper transcription unnecessarily.
- Clean up temporary local files (audio extracts, intermediate frames) after each
  job completes.

FRONTEND (React + Tailwind):
- Landing page: dark, minimal aesthetic, single accent color, confident typography —
  avoid the generic SaaS-template look.
- Auth pages (login/signup/forgot password/verify email).
- Dashboard: drag-and-drop upload, list of past videos with live status badges.
- Video detail page: ranked clip list with preview player, per-signal score
  breakdown (audio/scene/transcript, not just one composite number — this is more
  useful feedback for the user and doubles as a way to show the ML is doing
  something real, not a black box), multi-select for export.
- Responsive layout, usable on mobile browsers even though primary use is desktop.

DEPLOYMENT:
- docker-compose.yml running the full stack locally (FastAPI, Celery worker, Redis,
  Postgres, MinIO) with one command.
- Separate production-ready Dockerfiles for API and worker (multi-stage builds,
  non-root user, minimal base image).
- README covering setup, environment variables, and how the existing
  /highlight_detect module plugs into the Celery task layer.

DELIVERABLE STRUCTURE:
- /frontend — React app
- /backend — FastAPI app (routers, models, services, celery tasks clearly separated)
- /highlight_detect — existing validated ML module, imported by backend, not rewritten
- /infra — docker-compose, Dockerfiles, .env.example
- Unit tests at minimum for: the auth flow, the Celery task's handling of pipeline
  stage failures/retries, and the API layer's role-based access enforcement. The
  ML scoring logic already has its own validation from Phase 0 — don't duplicate
  that testing here, just test that the web layer calls it correctly.

Build iteratively: wire up auth and the database models first, then the upload +
Celery + pipeline integration, then the export/EDL generation, then the frontend
last. Confirm each layer works before moving to the next.
```

---

## What to watch for while this builds

- If Antigravity starts regenerating scoring logic instead of importing your Phase 0 module, stop it and point it back at the existing files. This is the most common failure mode with agentic tools on a project like this — they "helpfully" rewrite working code.
- The per-signal score breakdown (audio/scene/transcript shown separately, not just one number) is a small UI decision but it matters: it's the difference between a tool that feels like a black box and one that feels trustworthy, which matters a lot if you're pitching this to other editors later.
- Once auth + upload + processing is working end-to-end (even before the frontend is polished), test it against the same videos you validated in Phase 0. The scores should match what your CLI tool produced — if they don't, something broke in the integration, not the ML.

Once this is running, come back and I'll write the Phase 2 prompt (Tauri desktop packaging with offline local-processing mode) and Phase 3 (DaVinci Resolve plugin).
