# EduConnect Backend

FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL. Phase 1: full Google Classroom functionality.

## Requirements

- Python 3.11+
- PostgreSQL 14+ and Redis 6+ (or Docker)

## Run with Docker (recommended)

From the repository root:

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health and http://localhost:8000/health/ready

Stop with `docker compose down` (add `-v` to also delete data volumes).

## Run locally (without a backend container)

```bash
# 1. Start only the infrastructure
docker compose up -d postgres redis

# 2. Create a virtualenv and install dependencies
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Start the API with hot reload
uvicorn app.main:app --reload --port 8000
```

## Project layout

```text
app/
├── main.py          # FastAPI app factory, CORS, rate limiting, health
├── core/            # config, security, dependencies
├── db/              # engine, session, declarative base
├── models/          # SQLAlchemy models
├── schemas/         # Pydantic schemas
├── api/v1/          # routers (auth, users, classrooms, ...)
├── services/        # business logic
├── utils/           # helpers
└── websockets/      # realtime notifications
```

## Configuration

All settings come from environment variables / `.env` (see `.env.example`).
`JWT_SECRET` must be at least 32 characters and must not contain the placeholder
`change-me` when `ENVIRONMENT=production`.

Logging is configured with `LOG_LEVEL` and `LOG_FORMAT` (`auto` = JSON lines in
production/staging, readable text elsewhere). The per-IP limits for `/auth/*` are
configurable with `AUTH_RATE_LIMIT_REGISTER`, `AUTH_RATE_LIMIT_LOGIN`,
`AUTH_RATE_LIMIT_REFRESH`, `AUTH_RATE_LIMIT_LOGOUT` and `AUTH_RATE_LIMIT_ME`.

## API conventions

- Errors: `{"error": {"code": "not_found", "message": "…", "details": null}}`; `422` lists
  each problem in `details`, `429` adds `retry_after_seconds` and a `Retry-After` header.
- Request ids: every response carries `X-Request-ID` (send your own, 8–64 chars of
  `A-Za-z0-9._-`), and the same id is on every log line of that request.
- Pagination: `limit` (1–100) and `offset` (0–100000) on list endpoints; `GET /classrooms`
  returns the total in `X-Total-Count`.
- Security headers: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, a strict CSP,
  `Cache-Control: no-store` on API responses, and HSTS in production.
- Free text is normalised (NFC) and stripped of control characters and bidi overrides at
  the API boundary; HTML is escaped on output, never on input.

## Tests

```bash
pytest -q
```

## Migrations (available from STEP 2)

```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
```

----------------------------

# EduConnect

A Google-Classroom-style learning platform with an **accessibility mode for blind students**:
teachers upload PDF / DOCX / TXT material, the system turns it into chapter-organised audio
(an "audiobook") using free, open-source text-to-speech, and students listen from the app.

> **Status:** implemented up to and including **text-to-speech and the audiobook pipeline**.
> Speech-to-text (voice commands such as "go to physics chapter 2") and the voice-driven
> frontend are planned next (see [Roadmap](#roadmap)).

---

## 1. What is implemented

- **Core LMS:** auth (JWT, roles: admin / teacher / student), classrooms (join codes, archive),
  announcements, assignments, materials, quizzes, comments, notifications (REST + WebSocket),
  to-do, file uploads.
- **Accessibility:** per-user accessibility preferences, TTS endpoint with disk cache.
- **Audiobook pipeline:**
  1. Teacher uploads a file, then creates an audiobook (or attaches the file to a *material*, which auto-creates it).
  2. A Celery worker extracts structure (PDF outline / headings, DOCX headings, TXT chapters),
     removes running headers, splits text into ~800-1500 character segments.
  3. Each segment is synthesised with **Piper** (espeak-ng fallback), converted to MP3 with ffmpeg.
  4. API serves a **manifest** (chapters + segments + durations), **segment audio** (HTTP Range supported),
     **search**, and **playback progress**.
- Access rules: non-members get 404, students get 403 on teacher actions, archived classrooms are read-only.

## 2. Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16 (`pg_trgm`), Redis 7, Celery |
| TTS | Piper (`piper-tts`), espeak-ng fallback, ffmpeg |
| Frontend | React 19, TypeScript, Vite, Tailwind |
| Packaging | Docker Compose (postgres, redis, backend, worker, frontend) |

## 3. Repository layout

```text
educonnect/
  backend/            FastAPI app, Alembic migrations, tests, Dockerfile, requirements*.txt
  frontend/           React + Vite app (Dockerfile + nginx.conf)
  docs/
  docker-compose.yml
```

## 4. Prerequisites

- Git
- Docker Desktop (for Postgres/Redis and the full Docker run)
- Python 3.11 or 3.12 (the Docker image uses 3.11)
- **Node.js 22.12 or newer** (Vite 8 / Vitest 5 do not work on Node 20)
- Only if you run the Celery worker outside Docker: ffmpeg and (optionally) espeak-ng on your PATH

## 5. Clone the repository

```powershell
git clone https://github.com/AimaArshad/educonnect.git
cd educonnect
git checkout feature-fullstack-ai
```

## 6. Run locally (without Docker for the apps)

### 6.1 Start the databases

```powershell
docker compose up -d postgres redis
```

### 6.2 Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then edit values (database URL, secrets, ...)
alembic upgrade head            # create / update tables
uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
```

Optional: the audiobook **worker** locally (Celery's default pool does not work on Windows):

```powershell
celery -A app.worker.celery_app worker --loglevel=info -P solo
```

The worker needs the Piper voice files and ffmpeg; see the `PIPER_*` settings in `.env.example`.

### 6.3 Frontend

```powershell
cd frontend
node -v                          # must be 22.12 or newer
npm install
copy .env.example .env           # set the API URL (see the file)
npm run dev                      # http://localhost:5173
```

## 7. Run everything with Docker

```powershell
docker compose build
docker compose up -d postgres redis backend worker       # add "frontend" if you want it too
docker compose ps                                        # all Up / healthy
docker compose exec backend alembic upgrade head         # create tables (first run / after new migrations)
```

- API + Swagger: <http://localhost:8000/docs>
- Logs: `docker compose logs -f backend` and `docker compose logs -f worker`
- Stop: `docker compose stop` (keeps data). **Do not use `docker compose down -v` unless you want to wipe the database.**
- **Important:** do not run a local `uvicorn` on port 8000 at the same time as the Docker backend; both listen on 8000 and
  `localhost` may reach the wrong one.
- Code is baked into the images. After changing backend code run `docker compose build backend worker` and
  `docker compose up -d backend worker`.

Named volumes: `educonnect_audiobook_audio` (generated MP3s), `educonnect_tts_cache`, `educonnect_piper_voices`,
plus the uploads folder shared by backend and worker.

## 8. Tests

From `backend/` with the virtual environment active (PostgreSQL must be running):

```powershell
pytest -q                                   # full suite, about 15-20 minutes
pytest tests/test_audiobook_api.py -q       # audiobook API only
alembic check                               # must print "No new upgrade operations detected."
```

Tests use a temporary storage folder, so they do not write into your real `storage/`.

## 9. Try the audiobook flow in Swagger (<http://localhost:8000/docs>)

1. `POST /api/v1/auth/register` (role `teacher`), then `POST /api/v1/auth/login`. Click **Authorize** and paste the token
   (**access tokens expire after 15 minutes**; log in again when you get "Token has expired").
2. `POST /api/v1/classrooms` and note the classroom `id`.
3. `POST /api/v1/files/upload` with a small PDF, DOCX or TXT file (choose the file in the form). Note the file `id`.
4. `POST /api/v1/classrooms/{classroom_id}/audiobooks` with `{"file_id": "<file id>", "title": "My book"}`.
   Note the audiobook `id` (**not** the file id).
5. `GET /api/v1/audiobooks` until the status is `ready` (`queued` -> `synthesizing` -> `ready`, or `failed`).
6. `GET /api/v1/audiobooks/{audiobook_id}/manifest`, then `GET /api/v1/audiobooks/{audiobook_id}/segments/0/audio`.
7. To retry a failed build use `POST /api/v1/audiobooks/{audiobook_id}/rebuild` (the create endpoint is idempotent and
   will not re-queue an existing audiobook).

### Where the audio files are

Docker: `/app/storage/audiobooks/<audiobook_id>/<seq>.mp3` inside the `worker` and `backend` containers.

```powershell
docker compose exec worker ls -R /app/storage/audiobooks
docker compose cp worker:/app/storage/audiobooks/<audiobook_id>/0.mp3 .\0.mp3     # copy to your PC and play it
```

Local (no Docker): `backend/storage/audiobooks/<audiobook_id>/<seq>.mp3` (or the folder set in `AUDIOBOOK_AUDIO_DIR`).

## 10. Git workflow

```powershell
git status
git add -A
git commit -m "feat(scope): short description"
git push
```

Before committing check that `git status` shows no `.env`, `storage/` or `*.mp3` files. `requirements.txt` must stay UTF-8
(PowerShell's `>` can write UTF-16, which breaks pip and Docker).

## 11. Troubleshooting (problems already met)

| Symptom | Cause / fix |
|---|---|
| Register returns 500, log says "password cannot be longer than 72 bytes" | `bcrypt` 5.x is incompatible with `passlib`. `requirements.txt` pins `bcrypt==4.0.1`. |
| Swagger acts strangely / wrong user data | Two servers on port 8000 (local uvicorn and Docker). Stop one. `netstat -ano | findstr :8000` |
| Audiobook stays `queued` | Backend could not reach Redis (`localhost:6379` in the log). The backend service needs `CELERY_BROKER_URL=redis://redis:6379/2`. |
| Worker cannot write audio, "Permission denied" | Volume owned by root. The Dockerfile must create `/app/storage/audiobooks` before `chown`; remove the old volume once. |
| `Token has expired` | Access tokens last 15 minutes. Log in again and re-authorize. |
| Manifest / progress / search return 404 | You used the file id; use the audiobook id from the create response. |
| Docker build is huge and slow | Missing `.dockerignore` (`.venv`, `storage/`, `tests/`, `.env` must be excluded). |
| Worker shows `(unhealthy)` | Cosmetic; it inherits the API health check. Disable it for the worker in compose. |
| `Cannot find native binding` (rolldown) on `npm install` | Node is too old; install Node 22.12+. |

## 12. Deploying to Azure (outline)

This is a recommended architecture and command outline. Check names, SKUs and prices in the Azure portal before use.

| Component | Azure service |
|---|---|
| Container images | Azure Container Registry (ACR) |
| API (`backend`) | Azure Container Apps (external ingress, port 8000) |
| Celery `worker` | A second Container App, **no ingress**, same image, command `celery -A app.worker.celery_app worker ...` |
| Database | Azure Database for PostgreSQL - Flexible Server |
| Redis (cache + broker) | Azure Managed Redis (or Azure Cache for Redis) |
| Uploads + generated audio | Azure Files share mounted into both apps (API and worker must see the same files) |
| Frontend | Azure Static Web Apps (build `npm run build`) or a container with nginx |
| Secrets | Azure Key Vault / Container Apps secrets |

Steps:

```powershell
az login
az group create -n educonnect-rg -l <region>
az acr create -n <acrname> -g educonnect-rg --sku Basic
az acr build -r <acrname> -t educonnect-backend:1 ./backend           # one image serves API and worker
az postgres flexible-server create -g educonnect-rg -n <pgname> ...   # then create the database
az containerapp env create -n educonnect-env -g educonnect-rg -l <region>
# create the Azure Files share and register it in the environment (az containerapp env storage set ...)
az containerapp create -n educonnect-api ... --target-port 8000 --ingress external
az containerapp create -n educonnect-worker ... --command ... (no ingress)
```

Things that will bite if forgotten:

1. **pg_trgm:** allow the extension on the Flexible Server (server parameter `azure.extensions` includes `PG_TRGM`) before running migrations.
2. **Migrations:** run `alembic upgrade head` once as a job or one-off command against the Azure database before starting the API.
3. **Redis TLS:** managed Redis uses TLS (`rediss://...`); the Celery broker URL and the app `REDIS_URL` need the TLS form and
   the matching SSL options. Keep the long visibility timeout configured for the audiobook task.
4. **Shared storage:** mount the same Azure Files share for `STORAGE_DIR` and `AUDIOBOOK_AUDIO_DIR` in both container apps, with
   UID/GID matching the container user so the worker can write.
5. **Environment variables:** set `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, a strong `SECRET_KEY`, `CORS_ORIGINS` (your
   frontend URL), the environment name `production`, storage paths, Piper/Whisper settings. Use secrets for passwords.
6. **Sizing:** the worker (Piper, later faster-whisper) needs CPU and memory; start with 2 vCPU / 4 GB and measure.
7. **Frontend:** build with the production API URL and make sure HTTPS is used end to end (microphones require a secure context).

## 13. Roadmap

- **F** voice backend: faster-whisper transcription endpoint and a voice-command parser (play, pause, forward/backward 30 s,
  faster/slower, go to chapter / topic / page, spoken "not found" messages).
- **G** frontend voice base (browser speech recognition first, server transcription as fallback).
- **H** audiobook player with voice transport controls.
- **I** hardening, CI (GitHub Actions), end-to-end browser tests.
- Cleanup: show the build `error` to teachers, log worker failures, fail the audiobook if enqueue fails, pin all dependency versions in a lock file.