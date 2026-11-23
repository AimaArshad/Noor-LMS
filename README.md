# EduConnect

A Google-Classroom-style learning platform with an **accessibility mode for blind students**.
Teachers upload PDF / DOCX / TXT material; the system turns it into chapter-organised audio
(an "audiobook") with free, open-source text-to-speech; students listen in the app and control
everything **by voice or keyboard**. English only.

> **Status:** audiobook pipeline, voice backend, teacher screens, student player and app-wide voice
> navigation are implemented. Open items are listed in [Roadmap](#14-roadmap-and-known-limitations).

---

## 1. What is implemented

- **Core LMS:** auth (JWT; roles admin / teacher / student), classrooms (join codes, archive), announcements,
  assignments, materials, quizzes, comments, notifications, to-do, file uploads.
- **Audiobook pipeline (backend):**
  1. A teacher uploads a file and creates an audiobook in a classroom.
  2. A Celery worker extracts the structure. PDFs with bookmarks use them; PDFs without bookmarks use chapter-opener
     pages ("After studying this chapter...") and the Contents page; numbered ALL-CAPS headings become topics. DOCX uses
     headings, TXT uses "Chapter N" lines. Images are skipped (no OCR).
  3. Text is split into ~800-1500 character segments, each synthesised with **Piper** (espeak-ng fallback) and stored as MP3.
     Segments become playable progressively while the book is still building.
  4. The API serves a manifest (chapters, topics, segments, durations), segment audio (HTTP Range), search and playback progress.
- **Voice backend:** `POST /api/v1/voice/command` turns a sentence into an action (play, pause, stop, forward/backward 30 s,
  faster/slower, next/previous chapter, go to chapter / topic / page) with fuzzy book matching (rapidfuzz) and a spoken reply
  (including "not found" messages). `POST /api/v1/voice/transcribe` is a server fallback for speech-to-text (faster-whisper).
- **Frontend:**
  - Teacher: classroom **Audiobooks** tab with upload form (PDF/DOCX/TXT, 25 MB), progress bar, status badge, polling,
    Rebuild and Delete.
  - Student: **Audiobooks** library (`/audiobooks`) and **player** (`/audiobooks/:id`): sequential playback, chapter/topic list,
    +/-30 s across segments, speed 0.75x-2x, resume position, keyboard shortcuts.
  - **Voice:** header toggle "A11y: on/off", microphone button and the `V` key. Browser speech recognition first, server
    Whisper as fallback. Spoken replies use the browser's speech synthesis.
  - App-wide voice navigation: "open audiobooks", "go home", "open my classes", "play physics 2nd year" from any page.

## 2. Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16 (`pg_trgm`), Redis 7, Celery |
| Audio | Piper TTS (`piper-tts`), espeak-ng fallback, ffmpeg / ffprobe |
| Voice | rapidfuzz (command matching), faster-whisper `base.en` (int8, CPU) for server transcription |
| Frontend | React 19, TypeScript, Vite, Tailwind, TanStack Query, Vitest |
| Packaging | Docker Compose (postgres, redis, backend, worker, frontend) |

## 3. Repository layout

```text
educonnect/
  backend/    FastAPI app, Alembic migrations, tests, Dockerfile, requirements*.txt
  frontend/   React + Vite app (Dockerfile + nginx.conf)
  docs/
  docker-compose.yml
```

## 4. Prerequisites

- Git, Docker Desktop, Python 3.11 or 3.12 (Docker image uses 3.11)
- **Node.js 22.12 or newer** (Vite 8 / Vitest 5 do not work on Node 20)
- **Google Chrome** for voice control (browser speech recognition). Edge is not recommended for the demo.
- Only to run the Celery worker outside Docker: ffmpeg and (optionally) espeak-ng on PATH

## 5. Clone

```powershell
git clone https://github.com/AimaArshad/educonnect.git
cd educonnect
git checkout feature-fullstack-ai
```

## 6. Run the whole app with Docker (recommended for the demo)

```powershell
docker compose build
docker compose up -d postgres redis backend worker
docker compose ps                                       # all Up / healthy
docker compose exec backend alembic upgrade head        # first run / after new migrations
```

- API + Swagger: <http://localhost:8000/docs>
- Logs: `docker compose logs -f backend`, `docker compose logs -f worker`
- Stop: `docker compose stop` (keeps data). **Never run `docker compose down -v`** (it deletes the database and all audio).
- Do not run a local `uvicorn` on port 8000 while the Docker backend runs.
- Code is baked into the images: after changing backend code run `docker compose build backend worker` then
  `docker compose up -d backend worker`.
- Volumes: `educonnect_audiobook_audio` (MP3s), `educonnect_tts_cache`, `educonnect_piper_voices`, `educonnect_whisper_cache`,
  uploads, Postgres data.

Frontend (dev server, separate terminal):

```powershell
cd frontend
node -v                         # 22.12 or newer
npm install
copy .env.example .env          # API URL
npm run dev                     # http://localhost:5173  (open in Chrome)
```

## 7. Run the backend locally instead of in Docker

```powershell
docker compose up -d postgres redis
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The API and the Celery worker must run in the **same environment** (both Docker or both local): they share a queue
through Redis but not their file storage. Local worker: `celery -A app.worker.celery_app worker --loglevel=info -P solo`
(needs ffmpeg and the Piper voice files).

Pinned dependencies that matter: `bcrypt==4.0.1` (passlib), `av>=14,<16` (faster-whisper; `av` 19 breaks it),
`requirements.txt` must be saved as UTF-8.

## 8. Tests

```powershell
# backend (PostgreSQL must be running), from backend/ with the venv active
pytest -q
pytest tests/test_audiobook_api.py tests/test_voice_parser.py tests/test_voice_api.py -q
alembic check                    # must print "No new upgrade operations detected."

# frontend, from frontend/
npx vitest run
npm run build                    # type-checks (tsc -b) and builds
```

## 9. Using the app

**Teacher**
1. Register as `teacher`, create a class, open it, click the **Audiobooks** tab.
2. Upload a PDF/DOCX/TXT and give it a title. The card shows Queued -> Extracting -> Synthesizing -> Ready with a progress bar.
   Large books take long (a 186-page physics book: about 80 minutes for 346 minutes of audio). Short files take about a minute.
3. **Rebuild** re-queues a failed book; **Delete** removes it and its audio.

**Student**
1. Join the class with the code, then use **Audiobooks** in the top menu (or the class's Audiobooks tab) and press **Play**.
2. Player: Space play/pause, Left/Right skip 30 s, `[` / `]` slower/faster, `N` / `P` next/previous chapter, `V` voice.
   Chapters and topics are listed below the controls. The position is saved every 10 s and restored on the next visit.

### Voice commands (turn on **A11y**, press `V` or the microphone, then speak)

| Anywhere | Inside a book |
|---|---|
| "open audiobooks" / "what audiobooks do I have" | "play" / "pause" / "stop" / "resume" |
| "play physics 2nd year" | "forward" / "backward" (30 seconds) |
| "go home", "open my classes", "open to do" | "faster" / "slower" |
| "help" | "next chapter" / "previous chapter" |
| | "go to chapter two", "play topic kinetic theory", "play page 23" |
| | "go to physics chapter 2 class 1st year" |

Spoken replies, including "not found" messages, come from the backend. The microphone needs a secure context
(`localhost` is fine; production must use HTTPS).

## 10. Try the API in Swagger (<http://localhost:8000/docs>)

1. Register and log in, click **Authorize** (tokens expire after 15 minutes).
2. `POST /classrooms`, `POST /files/upload`, then `POST /classrooms/{id}/audiobooks` with `{"file_id": "...", "title": "..."}`.
3. `GET /audiobooks` until `ready`; `GET /audiobooks/{id}/manifest`; `GET /audiobooks/{id}/segments/0/audio`.
4. `POST /voice/command` with `{"text": "go to chapter two in physics 2nd year"}`. **Do not** send Swagger's placeholder
   `3fa85f64-...` as `audiobook_id`; delete the field or use a real id.
5. Copy audio to your PC: `docker compose cp worker:/app/storage/audiobooks/<id> .\audio`.

## 11. Demo-day checklist

Do this 30 minutes before:

1. Start Docker Desktop, then `docker compose up -d postgres redis backend worker`; `docker compose ps` shows everything Up.
2. `cd frontend; npm run dev`; open <http://localhost:5173> in **Chrome**.
3. Log in as the student, open **Audiobooks**: books show **Ready**. Press Play once to confirm sound.
4. Turn on **A11y**, allow the microphone, press `V` and say "help".
5. Have a teacher account ready and a **short** (1-2 page) file for a live upload (about a minute). Do not upload a large book live.
6. Close other tabs that use the microphone. Use speakers or headphones at moderate volume.

Suggested flow (about 5 minutes): teacher uploads the short file and the status changes to Ready -> log in as the student ->
"open audiobooks" -> "play physics 2nd year" -> "go to chapter two" -> "forward" -> "faster" -> "pause" -> reload and show resume.

## 12. Git workflow

```powershell
git status
git add -A
git commit -m "feat(scope): short description"
git push
```

Check that `git status` shows no `.env`, `storage/`, `*.mp3`, `physics_audio/` or helper scripts before committing.

## 13. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Register returns 500 ("password cannot be longer than 72 bytes") | `bcrypt` 5.x vs `passlib`; keep `bcrypt==4.0.1`. |
| Audiobook stays `queued` | The backend cannot reach Redis, or the worker is down. Backend needs `CELERY_BROKER_URL=redis://redis:6379/2`; check `docker compose logs worker`. |
| Audiobook `failed` | `GET /audiobooks` shows the `error` text. Fix the cause, then `POST /audiobooks/{id}/rebuild`. |
| Rebuild returns 409 | The book is queued/extracting/synthesizing. Delete it and upload again (stale-state fix is on the roadmap). |
| Whisper crashes with `metadata_errors` | `av` 19 installed. `pip install "av>=14,<16"`. |
| Voice says "open an audiobook first" | No book is open and none was named. Say "play physics 2nd year", or open a book first. |
| Voice does nothing in Edge or Firefox | Use Chrome; other browsers use the slower server fallback or have no speech recognition. |
| Voice does nothing after pressing `V` | Check microphone permission (lock icon in the address bar) and that **A11y** is on. |
| Player says "still being prepared" | That part of the book is not synthesised yet. It retries automatically every 5 seconds. |
| `docker compose` backend unreachable after `taskkill` of a PID | The Docker port forwarder was killed. `docker compose up -d --force-recreate backend` (or restart Docker Desktop). |
| `Token has expired` | Tokens last 15 minutes; log in again. |
| Console: `WebSocket ... /ws/notifications failed` | Notifications bell only; does not affect audio or voice. |
| `Cannot find native binding` on `npm install` | Node too old; install 22.12+. |
| Manifest/progress/search return 404 | You used the file id; use the audiobook id. |

## 14. Roadmap and known limitations

- **Scanned (image-only) documents** need OCR; they are marked "Needs OCR". Images inside documents are skipped.
- Cover, credits and the Contents page of a book are still read before chapter 1 (planned: skip pages before the first chapter).
- Topic titles of OCR-quality PDFs can contain noise.
- Only teachers can create audiobooks. **Planned:** students request audio for a file in their class (needs a permission change,
  rate limiting and a "generate this chapter first" option so a student does not wait for a whole book).
- Planned: stale-build recovery (rebuild after 30 minutes), voice not-found wording, **CI** (GitHub Actions), browser end-to-end tests
  and axe accessibility checks, dependency lock file, notification WebSocket fix.

## 15. Deploying to Azure (outline)

Recommended architecture; check names, SKUs and prices in the Azure portal before use.

| Component | Azure service |
|---|---|
| Images | Azure Container Registry |
| API | Azure Container Apps (external ingress, port 8000) |
| Celery worker | Second Container App, **no ingress**, same image, command `celery -A app.worker.celery_app worker ...` |
| Database | Azure Database for PostgreSQL - Flexible Server |
| Redis (cache + broker) | Azure Managed Redis (TLS) |
| Uploads + audio | Azure Files share mounted into both apps (API and worker must see the same files) |
| Frontend | Azure Static Web Apps (`npm run build`) or an nginx container |
| Secrets | Key Vault / Container Apps secrets |

```powershell
az login
az group create -n educonnect-rg -l <region>
az acr create -n <acrname> -g educonnect-rg --sku Basic
az acr build -r <acrname> -t educonnect-backend:1 ./backend        # one image for API and worker
az postgres flexible-server create -g educonnect-rg -n <pgname> ...
az containerapp env create -n educonnect-env -g educonnect-rg -l <region>
# create the Azure Files share and register it (az containerapp env storage set ...)
az containerapp create -n educonnect-api ... --target-port 8000 --ingress external
az containerapp create -n educonnect-worker ... (no ingress)
```

Things that bite if forgotten:

1. Allow `PG_TRGM` (server parameter `azure.extensions`) before migrations.
2. Run `alembic upgrade head` once against the Azure database before starting the API.
3. Redis TLS: `rediss://` URLs for `REDIS_URL` and `CELERY_BROKER_URL`; keep the long visibility timeout for the audiobook task.
4. Same Azure Files share for `STORAGE_DIR` and `AUDIOBOOK_AUDIO_DIR` in both apps, with matching UID/GID.
5. Set `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, a strong `SECRET_KEY`, `CORS_ORIGINS` (frontend URL), production environment name.
6. Worker sizing: Piper and faster-whisper need CPU and memory (start at 2 vCPU / 4 GB and measure); the Whisper model downloads on first use,
   so mount a persistent cache or bake the model into the image.
7. Serve the frontend over HTTPS (microphone requires a secure context) and build it with the production API URL.