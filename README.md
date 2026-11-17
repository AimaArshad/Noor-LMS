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
