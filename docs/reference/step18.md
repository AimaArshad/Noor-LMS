```ts
STEP 18: Polish and ship
Four decisions shape this step:
Two compose files. 
odocker-compose.yml is the production-like stack: Postgres, Redis, the backend and the built React app served by nginx.
odocker-compose.dev.yml is an opt-in overlay for hot reload (uvicorn --reload and the Vite dev server).
oThe frontend overlay uses the !override tag, which needs Docker Compose ≥ 2.24.
Configuration. 
oThe stack reads a root .env and no longer reads backend/.env. backend/.env is still used for running uvicorn on your host.
oJWT_SECRET is required, and compose refuses to start without it.
Migrations run on container start (docker-entrypoint.sh), so a fresh clone needs no manual alembic step.
Seed emails use @example.com. The email validator rejects .test domains, so they would not be able to log in.
I have not run ruff or ESLint over the whole codebase. The first CI run may flag a few unused imports or hook warnings, which ruff check --fix and npm run lint -- --fix handle.
Files in this step
educonnect/
├── .env.example                          ← NEW
├── .gitattributes                        ← NEW
├── .gitignore                            ← NEW
├── Makefile                              ← REPLACE
├── README.md                             ← NEW
├── docker-compose.yml                    ← REPLACE
├── docker-compose.dev.yml                ← NEW
├── .github/workflows/ci.yml              ← NEW
├── backend/
│   ├── Dockerfile                        ← REPLACE
│   ├── docker-entrypoint.sh              ← NEW
│   ├── requirements-dev.txt              ← REPLACE (+ ruff)
│   ├── ruff.toml                         ← NEW
│   └── scripts/{__init__,seed}.py        ← NEW
└── frontend/
    ├── package.json                      ← REPLACE (+ lint, test)
    ├── vite.config.ts                    ← REPLACE (+ vitest)
    ├── eslint.config.js                  ← NEW
    ├── nginx.conf                        ← REPLACE
    └── src/
        ├── lib/{format,files}.test.ts
        ├── api/errors.test.ts
        └── features/
            ├── todo/grouping.test.ts
            ├── quizzes/schemas.test.ts
            └── assignments/schemas.test.ts          ← all NEW
cd educonnect
mkdir -p .github/workflows backend/scripts
touch backend/scripts/__init__.py
Docker
# Production-like stack: nginx (React build) + FastAPI + PostgreSQL + Redis.
#   cp .env.example .env     # then set JWT_SECRET
#   docker compose up --build -d
# Hot-reload development: see docker-compose.dev.yml.
name: educonnect

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: educonnect
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-educonnect}
      POSTGRES_DB: educonnect
    ports:
      - "127.0.0.1:5432:5432" # localhost only; lets you run uvicorn on the host too
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U educonnect -d educonnect"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build:
      context: ./backend
    restart: unless-stopped
    environment:
      ENVIRONMENT: ${ENVIRONMENT:-development}
      DEBUG: "false"
      # URL-safe characters only in POSTGRES_PASSWORD (it is embedded in this URL).
      DATABASE_URL: postgresql+asyncpg://educonnect:${POSTGRES_PASSWORD:-educonnect}@postgres:5432/educonnect
      REDIS_URL: redis://redis:6379/0
      RATE_LIMIT_STORAGE_URI: redis://redis:6379/1
      JWT_SECRET: ${JWT_SECRET:?Set JWT_SECRET in .env (python -c "import secrets; print(secrets.token_urlsafe(64))")}
      ACCESS_TOKEN_EXPIRE_MINUTES: ${ACCESS_TOKEN_EXPIRE_MINUTES:-15}
      REFRESH_TOKEN_EXPIRE_DAYS: ${REFRESH_TOKEN_EXPIRE_DAYS:-7}
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:8080,http://localhost:5173}
      STORAGE_DIR: /app/storage
    ports:
      - "8000:8000"
    volumes:
      - storage_data:/app/storage
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    # ONE uvicorn worker: the WebSocket connection registry lives in process memory.

  frontend:
    build:
      context: ./frontend
      target: prod
      args:
        # Vite inlines these at BUILD time. The browser calls the backend directly.
        VITE_API_URL: ${VITE_API_URL:-http://localhost:8000/api/v1}
        VITE_WS_URL: ${VITE_WS_URL:-ws://localhost:8000}
    restart: unless-stopped
    ports:
      - "8080:80"
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1/ || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
  storage_data:
# Hot-reload overlay (needs Docker Compose >= 2.24 for `!override`):
#   docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
# Backend: http://localhost:8000   Frontend (Vite): http://localhost:5173
services:
  backend:
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --proxy-headers
    volumes:
      - ./backend/app:/app/app
      - ./backend/alembic:/app/alembic
      - ./backend/scripts:/app/scripts
      - storage_data:/app/storage

  frontend:
    build:
      target: dev
    environment:
      VITE_API_URL: ${VITE_API_URL:-http://localhost:8000/api/v1}
      VITE_WS_URL: ${VITE_WS_URL:-ws://localhost:8000}
      CHOKIDAR_USEPOLLING: "true" # file watching inside Docker on Windows/macOS
    ports: !override
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules # keep the container's own node_modules
    healthcheck:
      disable: true
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Non-root user
RUN addgroup --system app && adduser --system --ingroup app app

# Install dependencies first for better layer caching (runtime only; no test tools)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code (alembic/, scripts/, app/, ...)
COPY . .

# Writable storage dir owned by the app user
RUN mkdir -p /app/storage && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

# Applies migrations, then starts the command below (set RUN_MIGRATIONS=false to skip).
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Applying database migrations..."
  alembic upgrade head
fi

exec "$@"
# The entrypoint runs under /bin/sh in Linux: CRLF line endings would break it.
*.sh text eol=lf
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;

  gzip on;
  gzip_types text/css application/javascript application/json image/svg+xml;

  add_header X-Content-Type-Options "nosniff" always;
  add_header X-Frame-Options "DENY" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;

  # Hashed build assets: cache for a year
  location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    add_header X-Content-Type-Options "nosniff" always;
    try_files $uri =404;
  }

  # Single-page app: every other path serves index.html (React Router handles it)
  location / {
    add_header Cache-Control "no-cache";
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    try_files $uri /index.html;
  }
}
# Copy to `.env` (same folder as docker-compose.yml). Docker Compose reads it automatically.

# REQUIRED. Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"
JWT_SECRET=

# development keeps /docs and the dev-only /static/uploads mount.
# production disables both (and refuses a JWT_SECRET containing "change-me").
ENVIRONMENT=development

# URL-safe characters only (it is embedded in DATABASE_URL).
POSTGRES_PASSWORD=educonnect

ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Origins allowed to call the API from a browser (comma separated).
CORS_ORIGINS=http://localhost:8080,http://localhost:5173

# Baked into the frontend BUILD. The browser calls the backend directly.
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000
.env
backend/.env
frontend/.env
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
.coverage
backend/storage/*
!backend/storage/.gitkeep
node_modules/
dist/
Seed script
"""Seed demo data: 1 admin, 2 teachers, 5 students and 2 classrooms with content.

Usage (from backend/, or inside the container):

    python -m scripts.seed            # seed once; does nothing if already seeded
    python -m scripts.seed --reset    # delete the seeded users/classrooms, then seed again

Environment: SEED_PASSWORD (default "Passw0rd!"). Emails use example.com, which is reserved
and accepted by the API's email validator (``.test`` addresses are rejected).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models import (
    Announcement,
    Assignment,
    AssignmentState,
    Classroom,
    ClassroomMember,
    Comment,
    CommentTarget,
    Material,
    MemberRole,
    Notification,
    QuestionType,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizOption,
    QuizQuestion,
    Submission,
    SubmissionState,
    TodoRefType,
    User,
    UserRole,
)
from app.services import todo_sync
from app.utils.quiz_grading import grade_answer

DEFAULT_PASSWORD = "Passw0rd!"

ADMIN = ("admin@example.com", "Alex Admin")
TEACHERS = [("rivera@example.com", "Maria Rivera"), ("chen@example.com", "David Chen")]
STUDENTS = [
    ("sam@example.com", "Sam Okafor"),
    ("priya@example.com", "Priya Patel"),
    ("liam@example.com", "Liam Murphy"),
    ("aisha@example.com", "Aisha Khan"),
    ("noah@example.com", "Noah Garcia"),
]
SEED_EMAILS = [ADMIN[0], *(e for e, _ in TEACHERS), *(e for e, _ in STUDENTS)]


# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class QuestionSpec:
    prompt: str
    type: QuestionType
    points: int
    options: tuple[tuple[str, bool], ...]


@dataclass(frozen=True)
class AssignmentSpec:
    title: str
    description: str
    due_in_days: int | None
    points: int
    state: AssignmentState


@dataclass(frozen=True)
class ClassSpec:
    name: str
    section: str
    subject: str
    room: str
    join_code: str
    announcements: tuple[str, ...]
    materials: tuple[tuple[str, str], ...]
    assignments: tuple[AssignmentSpec, ...]
    quiz_title: str
    quiz_description: str
    quiz_minutes: int
    quiz_retake: bool
    quiz_due_in_days: int
    questions: tuple[QuestionSpec, ...]


P, D = AssignmentState.PUBLISHED, AssignmentState.DRAFT
MCQ, TF, SA = QuestionType.MCQ, QuestionType.TRUE_FALSE, QuestionType.SHORT_ANSWER

ALGEBRA = ClassSpec(
    name="Algebra I",
    section="Period 1",
    subject="Mathematics",
    room="B-12",
    join_code="ALGEBRA1",
    announcements=(
        "Welcome to Algebra I! Please bring a calculator on Monday.",
        "Reminder: Quiz 1 is open this week. You have 10 minutes once you start.",
    ),
    materials=(
        ("Syllabus", "Course outline, grading policy and schedule."),
        ("Solving equations cheat sheet", "A one-page summary of the methods we cover."),
    ),
    assignments=(
        AssignmentSpec("Linear equations practice", "Solve problems 1-20 from worksheet 3. Show your steps.", -3, 20, P),
        AssignmentSpec("Graphing lines project", "Graph three lines and describe the slope and intercept of each.", 5, 50, P),
        AssignmentSpec("Unit 2 review (draft)", "Review problems for the next unit.", 14, 30, D),
    ),
    quiz_title="Quiz 1: Solving equations",
    quiz_description="Ten minutes. Calculators are allowed.",
    quiz_minutes=10,
    quiz_retake=False,
    quiz_due_in_days=7,
    questions=(
        QuestionSpec("What is x if 2x + 3 = 11?", MCQ, 2, (("3", False), ("4", True), ("5", False), ("8", False))),
        QuestionSpec("The slope of y = 3x - 2 is 3.", TF, 1, (("True", True), ("False", False))),
        QuestionSpec("What is 5 squared?", SA, 1, (("25", True),)),
    ),
)

BIOLOGY = ClassSpec(
    name="Biology Basics",
    section="Period 3",
    subject="Science",
    room="Lab 2",
    join_code="BIOLOGY1",
    announcements=(
        "Welcome to Biology Basics! The lab safety rules are in the materials section.",
        "Field trip permission slips are due on Friday.",
    ),
    materials=(
        ("Lab safety rules", "Read these before our first lab session."),
        ("Cell structure guide", "Labelled diagrams of plant and animal cells."),
    ),
    assignments=(
        AssignmentSpec("Cell diagram", "Draw and label an animal cell with at least eight parts.", -2, 25, P),
        AssignmentSpec("Photosynthesis essay", "Write 300 words explaining how plants make food.", 7, 50, P),
        AssignmentSpec("Ecosystem poster (draft)", "Poster project for the ecology unit.", 21, 40, D),
    ),
    quiz_title="Quiz 1: Cells",
    quiz_description="Fifteen minutes. You may retake it once you finish.",
    quiz_minutes=15,
    quiz_retake=True,
    quiz_due_in_days=10,
    questions=(
        QuestionSpec(
            "Which organelle produces most of a cell's ATP?",
            MCQ,
            2,
            (("Nucleus", False), ("Mitochondrion", True), ("Ribosome", False), ("Golgi apparatus", False)),
        ),
        QuestionSpec("Plant cells have a cell wall.", TF, 1, (("True", True), ("False", False))),
        QuestionSpec("What is the green pigment in plants called?", SA, 2, (("chlorophyll", True),)),
    ),
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check_password(password: str) -> str:
    """Same rules as the API: 8-72 bytes, at least one letter and one digit."""
    ok = (
        8 <= len(password)
        and len(password.encode("utf-8")) <= 72
        and any(c.isalpha() for c in password)
        and any(c.isdigit() for c in password)
    )
    if not ok:
        raise SystemExit("SEED_PASSWORD must be 8-72 bytes with at least one letter and one digit.")
    return password


def _build_attempt(quiz: Quiz, student: User, *, correct: bool, started_at: datetime) -> QuizAttempt:
    """A submitted attempt graded with the same function the API uses."""
    total = Decimal("0")
    answers: list[QuizAnswer] = []
    for question in quiz.questions:
        if question.type == QuestionType.SHORT_ANSWER:
            accepted = next((o.text for o in question.options if o.is_correct), "")
            graded = grade_answer(question, None, accepted if correct else "no idea")
        else:
            option = next(o for o in question.options if o.is_correct == correct)
            graded = grade_answer(question, option.id, None)
        total += graded.points or Decimal("0")
        answers.append(
            QuizAnswer(
                question_id=question.id,
                selected_option_id=graded.selected_option_id,
                answer_text=graded.answer_text,
                is_correct=graded.is_correct,
                points_awarded=graded.points,
            )
        )
    return QuizAttempt(
        quiz_id=quiz.id,
        student_id=student.id,
        started_at=started_at,
        submitted_at=started_at + timedelta(minutes=4),
        score=total,
        answers=answers,
    )


async def _wipe(session: AsyncSession) -> None:
    """Delete the seeded classrooms and users (ORM deletes, so comments are cleaned up too)."""
    users = list((await session.scalars(select(User).where(User.email.in_(SEED_EMAILS)))).all())
    ids = [u.id for u in users]
    if ids:
        for classroom in (await session.scalars(select(Classroom).where(Classroom.owner_id.in_(ids)))).all():
            await session.delete(classroom)
        await session.flush()
        for user in users:
            await session.delete(user)
    await session.commit()


async def _populate(
    session: AsyncSession, spec: ClassSpec, teacher: User, students: list[User], now: datetime
) -> Classroom:
    """One classroom with announcements, materials, assignments, submissions, a quiz and activity."""
    classroom = Classroom(
        name=spec.name,
        section=spec.section,
        subject=spec.subject,
        room=spec.room,
        owner_id=teacher.id,
        join_code=spec.join_code,
    )
    session.add(classroom)
    await session.flush()

    session.add(ClassroomMember(classroom_id=classroom.id, user_id=teacher.id, role=MemberRole.TEACHER))
    session.add_all(
        ClassroomMember(classroom_id=classroom.id, user_id=s.id, role=MemberRole.STUDENT) for s in students
    )
    await session.flush()

    # created_at is set explicitly: rows of one transaction would otherwise share now().
    announcements = [
        Announcement(
            classroom_id=classroom.id,
            author_id=teacher.id,
            content=text,
            created_at=now - timedelta(days=(len(spec.announcements) - i) * 2),
        )
        for i, text in enumerate(spec.announcements)
    ]
    materials = [
        Material(
            classroom_id=classroom.id,
            title=title,
            description=description,
            created_at=now - timedelta(days=(len(spec.materials) - i) * 3),
        )
        for i, (title, description) in enumerate(spec.materials)
    ]
    assignments = [
        Assignment(
            classroom_id=classroom.id,
            title=a.title,
            description=a.description,
            due_at=now + timedelta(days=a.due_in_days) if a.due_in_days is not None else None,
            max_points=a.points,
            state=a.state,
            created_at=now - timedelta(days=10) + timedelta(hours=i),
        )
        for i, a in enumerate(spec.assignments)
    ]
    session.add_all([*announcements, *materials, *assignments])
    await session.flush()

    for assignment in assignments:
        if assignment.state == AssignmentState.PUBLISHED:
            await todo_sync.create_for_students(
                session,
                classroom_id=classroom.id,
                ref_type=TodoRefType.ASSIGNMENT,
                ref_id=assignment.id,
                title=assignment.title,
                due_at=assignment.due_at,
            )

    def link(assignment: Assignment) -> str:
        return f"/classrooms/{classroom.id}/assignments/{assignment.id}"

    # --- submissions: one returned, one graded (hidden from the student), one to grade -------
    first, second = assignments[0], assignments[1]
    first_due = first.due_at or now
    ratio = lambda r: (Decimal(first.max_points) * Decimal(r)).quantize(Decimal("0.01"))  # noqa: E731
    session.add_all(
        [
            Submission(
                assignment_id=first.id,
                student_id=students[0].id,
                content="Here are my worked solutions for all twenty problems.",
                state=SubmissionState.RETURNED,
                grade=ratio("0.90"),
                feedback="Great work. Watch your signs in problem 14.",
                submitted_at=first_due - timedelta(days=1),
                graded_at=now - timedelta(days=2),
                graded_by=teacher.id,
            ),
            Submission(
                assignment_id=first.id,
                student_id=students[1].id,
                content="My answers are attached below. Problem 9 was hard.",
                state=SubmissionState.GRADED,
                grade=ratio("0.75"),
                feedback="Good effort. See me about problem 9.",
                submitted_at=first_due - timedelta(hours=5),
                graded_at=now - timedelta(days=1),
                graded_by=teacher.id,
            ),
            Submission(
                assignment_id=first.id,
                student_id=students[2].id,
                content="Sorry this is a bit late, here is my work.",
                state=SubmissionState.TURNED_IN,
                submitted_at=first_due + timedelta(hours=3),
            ),
            Submission(
                assignment_id=second.id,
                student_id=students[0].id,
                content="I graphed the three lines and wrote a short description of each.",
                state=SubmissionState.TURNED_IN,
                submitted_at=now - timedelta(hours=1),
            ),
        ]
    )

    # --- quiz with two submitted attempts ---------------------------------------------------
    quiz = Quiz(
        classroom_id=classroom.id,
        title=spec.quiz_title,
        description=spec.quiz_description,
        time_limit_minutes=spec.quiz_minutes,
        due_at=now + timedelta(days=spec.quiz_due_in_days),
        published=True,
        allow_retake=spec.quiz_retake,
    )
    quiz.questions = [
        QuizQuestion(
            prompt=q.prompt,
            type=q.type,
            points=Decimal(q.points),
            order_index=i,
            options=[QuizOption(text=text, is_correct=ok, order_index=j) for j, (text, ok) in enumerate(q.options)],
        )
        for i, q in enumerate(spec.questions)
    ]
    session.add(quiz)
    await session.flush()  # assigns ids, which the attempts need
    session.add(_build_attempt(quiz, students[0], correct=True, started_at=now - timedelta(days=1, hours=2)))
    session.add(_build_attempt(quiz, students[1], correct=False, started_at=now - timedelta(hours=20)))
    await todo_sync.create_for_students(
        session,
        classroom_id=classroom.id,
        ref_type=TodoRefType.QUIZ,
        ref_id=quiz.id,
        title=quiz.title,
        due_at=quiz.due_at,
    )

    # --- comments ---------------------------------------------------------------------------
    session.add_all(
        [
            Comment(
                author_id=students[0].id,
                target_type=CommentTarget.ANNOUNCEMENT,
                target_id=announcements[0].id,
                body="Thanks! Do we need graph paper?",
                created_at=now - timedelta(days=1, hours=3),
            ),
            Comment(
                author_id=teacher.id,
                target_type=CommentTarget.ANNOUNCEMENT,
                target_id=announcements[0].id,
                body="Yes, bring a few sheets. I will have spares too.",
                created_at=now - timedelta(days=1, hours=2),
            ),
            Comment(
                author_id=students[1].id,
                target_type=CommentTarget.ASSIGNMENT,
                target_id=second.id,
                body="Can we use a graphing app, or must it be on paper?",
                created_at=now - timedelta(hours=6),
            ),
        ]
    )

    # --- notifications ----------------------------------------------------------------------
    session.add_all(
        [
            Notification(
                user_id=teacher.id,
                title=f"{students[0].full_name} turned in {first.title}",
                type="submission_turned_in",
                link=link(first),
                is_read=True,
                created_at=first_due - timedelta(days=1),
            ),
            Notification(
                user_id=teacher.id,
                title=f"{students[2].full_name} turned in {first.title}",
                type="submission_turned_in",
                link=link(first),
                created_at=first_due + timedelta(hours=3),
            ),
            Notification(
                user_id=teacher.id,
                title=f"{students[0].full_name} turned in {second.title}",
                type="submission_turned_in",
                link=link(second),
                created_at=now - timedelta(hours=1),
            ),
            Notification(
                user_id=students[0].id,
                title=f"Your work on {first.title} was returned",
                type="submission_returned",
                link=link(first),
                created_at=now - timedelta(days=2),
            ),
        ]
        + [
            Notification(
                user_id=s.id,
                title=f"New material: {materials[-1].title}",
                type="material_posted",
                link=f"/classrooms/{classroom.id}/materials/{materials[-1].id}",
                created_at=materials[-1].created_at,
            )
            for s in students
        ]
    )
    await session.flush()
    return classroom


async def _seed(session: AsyncSession, password: str) -> list[Classroom]:
    password_hash = hash_password(password)  # one bcrypt hash shared by all demo users

    def make(email: str, name: str, role: UserRole) -> User:
        return User(email=email, hashed_password=password_hash, full_name=name, role=role)

    admin = make(*ADMIN, UserRole.ADMIN)
    teachers = [make(e, n, UserRole.TEACHER) for e, n in TEACHERS]
    students = [make(e, n, UserRole.STUDENT) for e, n in STUDENTS]
    session.add_all([admin, *teachers, *students])
    await session.flush()

    now = _now()
    algebra = await _populate(session, ALGEBRA, teachers[0], students[0:3], now)
    biology = await _populate(session, BIOLOGY, teachers[1], students[2:5], now)  # Liam is in both
    await session.commit()
    return [algebra, biology]


async def run(reset: bool, allow_production: bool) -> int:
    if settings.is_production and not allow_production:
        print("Refusing to seed a production environment (pass --allow-production to override).")
        return 2
    password = _check_password(os.getenv("SEED_PASSWORD", DEFAULT_PASSWORD))

    try:
        async with AsyncSessionLocal() as session:
            exists = await session.scalar(select(User.id).where(User.email == ADMIN[0]))
            if exists is not None and not reset:
                print("Already seeded. Use --reset to delete the demo data and seed again.")
                return 0
            if reset:
                await _wipe(session)
            classrooms = await _seed(session, password)
    finally:
        await engine.dispose()

    print("\nDemo data created. Password for every account:", password)
    print(f"  {'role':<9} {'email':<24} name")
    for role, rows in (("admin", [ADMIN]), ("teacher", TEACHERS), ("student", STUDENTS)):
        for email, name in rows:
            print(f"  {role:<9} {email:<24} {name}")
    print("\nClassrooms (students can join with the code):")
    for classroom in classrooms:
        print(f"  {classroom.name:<16} join code {classroom.join_code}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed EduConnect demo data.")
    parser.add_argument("--reset", action="store_true", help="delete the seeded users/classrooms first")
    parser.add_argument("--allow-production", action="store_true", help="allow ENVIRONMENT=production")
    args = parser.parse_args()
    return asyncio.run(run(args.reset, args.allow_production))


if __name__ == "__main__":
    sys.exit(main())
Lint configuration
target-version = "py311"
line-length = 100
extend-exclude = ["alembic/versions"]

[lint]
# Deliberately small: real errors only (pyflakes + syntax/core pycodestyle).
# Style rules can be added later without breaking CI on day one.
select = ["E4", "E7", "E9", "F"]
-r requirements.txt

pytest==8.3.4
pytest-asyncio==0.25.0
pytest-cov==6.0.0
httpx==0.28.1
ruff==0.8.4
{
  "name": "educonnect-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "typecheck": "tsc -b",
    "lint": "eslint .",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@hookform/resolvers": "^3.10.0",
    "@radix-ui/react-dialog": "^1.1.2",
    "@radix-ui/react-label": "^2.1.0",
    "@radix-ui/react-slot": "^1.1.0",
    "@tanstack/react-query": "^5.62.0",
    "axios": "^1.7.9",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.468.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-hook-form": "^7.54.2",
    "react-router-dom": "^6.28.0",
    "tailwind-merge": "^2.5.5",
    "tailwindcss-animate": "^1.0.7",
    "zod": "^3.24.1",
    "zustand": "^5.0.2"
  },
  "devDependencies": {
    "@eslint/js": "^9.17.0",
    "@types/node": "^22.10.0",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.17.0",
    "eslint-plugin-react-hooks": "^5.1.0",
    "globals": "^15.14.0",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "typescript": "~5.6.3",
    "typescript-eslint": "^8.18.2",
    "vite": "^6.0.3",
    "vitest": "^3.0.5"
  }
}
import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // 5173 is the origin the backend's CORS_ORIGINS allows by default.
  server: { host: true, port: 5173, strictPort: true },
  preview: { port: 5173 },
  // Unit tests cover pure logic (grouping, validation, formatting); no DOM needed.
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-hooks/exhaustive-deps": "warn",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    },
  },
);
Frontend tests
import { describe, expect, it } from "vitest";

import { groupTodos } from "@/features/todo/grouping";
import type { TodoItem } from "@/types";

// Local-time constructors keep these tests independent of the machine's time zone.
const NOW = new Date(2026, 9, 11, 10, 0, 0); // Sun 11 Oct 2026, 10:00

function item(id: string, due: Date | null, done = false): TodoItem {
  return {
    id,
    user_id: "u1",
    title: id,
    due_at: due ? due.toISOString() : null,
    ref_type: "assignment",
    ref_id: id,
    is_done: done,
    created_at: NOW.toISOString(),
    classroom_id: null,
    classroom_name: null,
    link: null,
    is_overdue: false,
  };
}

const ids = (groups: ReturnType<typeof groupTodos>, key: string) =>
  groups.find((g) => g.key === key)?.items.map((i) => i.id);

describe("groupTodos", () => {
  it("splits items into overdue / today / this week / later / done", () => {
    const groups = groupTodos(
      [
        item("past-today", new Date(2026, 9, 11, 9, 0)),
        item("tonight", new Date(2026, 9, 11, 18, 0)),
        item("tomorrow", new Date(2026, 9, 12, 8, 0)),
        item("day-6", new Date(2026, 9, 17, 23, 0)),
        item("day-7", new Date(2026, 9, 18, 0, 0)),
        item("no-date", null),
        item("finished", new Date(2026, 9, 1), true),
      ],
      NOW,
    );

    expect(groups.map((g) => g.key)).toEqual(["overdue", "today", "week", "later", "done"]);
    expect(ids(groups, "overdue")).toEqual(["past-today"]);
    expect(ids(groups, "today")).toEqual(["tonight"]);
    expect(ids(groups, "week")).toEqual(["tomorrow", "day-6"]);
    expect(ids(groups, "later")).toEqual(["day-7", "no-date"]); // undated items come last
    expect(ids(groups, "done")).toEqual(["finished"]);
  });

  it("sorts each group by due date, then title", () => {
    const groups = groupTodos(
      [
        item("b", new Date(2026, 9, 5)),
        item("a", new Date(2026, 9, 5)),
        item("older", new Date(2026, 9, 1)),
      ],
      NOW,
    );
    expect(ids(groups, "overdue")).toEqual(["older", "a", "b"]);
  });

  it("returns every group, even when empty", () => {
    const groups = groupTodos([], NOW);
    expect(groups).toHaveLength(5);
    expect(groups.every((g) => g.items.length === 0)).toBe(true);
  });
});
import { describe, expect, it } from "vitest";

import { formatPoints, toIsoFromLocalInput } from "@/lib/format";

describe("toIsoFromLocalInput", () => {
  it("returns undefined for empty or invalid input", () => {
    expect(toIsoFromLocalInput("")).toBeUndefined();
    expect(toIsoFromLocalInput("not a date")).toBeUndefined();
  });

  it("converts a datetime-local value to a UTC ISO string", () => {
    const value = "2030-01-01T10:00";
    expect(toIsoFromLocalInput(value)).toBe(new Date(value).toISOString());
    expect(toIsoFromLocalInput(value)).toMatch(/Z$/);
  });
});

describe("formatPoints", () => {
  it("shows whole numbers without decimals and others with two", () => {
    expect(formatPoints(45)).toBe("45");
    expect(formatPoints(8.5)).toBe("8.50");
  });
});
import { describe, expect, it } from "vitest";

import { extensionOf, formatBytes, validateFile } from "@/lib/files";

describe("validateFile", () => {
  it("accepts allowed types in any letter case", () => {
    expect(validateFile(new File(["x"], "notes.pdf"))).toBeNull();
    expect(validateFile(new File(["x"], "PHOTO.JPG"))).toBeNull();
  });

  it("rejects disallowed extensions", () => {
    expect(validateFile(new File(["x"], "run.exe"))).toMatch(/not allowed/);
    expect(validateFile(new File(["x"], "page.html"))).toMatch(/not allowed/);
    expect(validateFile(new File(["x"], "README"))).toMatch(/not allowed/);
  });

  it("rejects empty and oversized files", () => {
    expect(validateFile(new File([], "empty.txt"))).toMatch(/empty/);
    const big = new File(["x"], "big.txt");
    Object.defineProperty(big, "size", { value: 26 * 1024 * 1024 });
    expect(validateFile(big)).toMatch(/larger than 25 MB/);
  });
});

describe("helpers", () => {
  it("extensionOf", () => {
    expect(extensionOf("a.TAR.GZ")).toBe(".gz");
    expect(extensionOf("noext")).toBe("");
  });

  it("formatBytes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});
import { AxiosError, type AxiosResponse } from "axios";
import { describe, expect, it } from "vitest";

import { getErrorMessage, getStatus } from "@/api/errors";

function httpError(status: number, data: unknown): AxiosError {
  const response = { status, data, statusText: "", headers: {}, config: {} } as unknown as AxiosResponse;
  return new AxiosError("failed", "ERR_BAD_REQUEST", undefined, undefined, response);
}

describe("getStatus", () => {
  it("reads the HTTP status of axios errors only", () => {
    expect(getStatus(httpError(409, {}))).toBe(409);
    expect(getStatus(new AxiosError("Network Error"))).toBeUndefined();
    expect(getStatus(new Error("boom"))).toBeUndefined();
  });
});

describe("getErrorMessage", () => {
  it("uses a string `detail` from the API", () => {
    expect(getErrorMessage(httpError(409, { detail: "Email already registered" }))).toBe("Email already registered");
  });

  it("joins 422 validation issues, dropping the `body` prefix", () => {
    const error = httpError(422, { detail: [{ loc: ["body", "email"], msg: "invalid email" }] });
    expect(getErrorMessage(error)).toBe("email: invalid email");
  });

  it("explains network failures and rate limits", () => {
    expect(getErrorMessage(new AxiosError("Network Error", "ERR_NETWORK"))).toMatch(/Cannot reach the server/);
    expect(getErrorMessage(httpError(429, {}))).toMatch(/Too many requests/);
  });

  it("handles plain errors and unknown values", () => {
    expect(getErrorMessage(new Error("boom"))).toBe("boom");
    expect(getErrorMessage("weird", "fallback text")).toBe("fallback text");
  });
});
import { describe, expect, it } from "vitest";

import { newQuestion, quizFormSchema, toPayload, type QuizFormValues } from "@/features/quizzes/schemas";

const base: QuizFormValues = {
  title: "Quiz 1",
  description: "",
  minutes: "",
  due: "",
  allowRetake: false,
  publish: false,
  questions: [],
};

const mcq = (overrides: Partial<QuizFormValues["questions"][number]> = {}): QuizFormValues["questions"][number] => ({
  type: "mcq",
  prompt: "2+2?",
  points: "2",
  correctIndex: 1,
  options: [{ text: "3" }, { text: "4" }],
  ...overrides,
});

describe("quizFormSchema", () => {
  it("accepts a valid multiple-choice quiz", () => {
    expect(quizFormSchema.safeParse({ ...base, questions: [mcq()] }).success).toBe(true);
  });

  it("rejects duplicate options (case-insensitive) and too few options", () => {
    const duplicates = quizFormSchema.safeParse({
      ...base,
      questions: [mcq({ options: [{ text: "A" }, { text: "a" }] })],
    });
    expect(duplicates.success).toBe(false);

    const tooFew = quizFormSchema.safeParse({ ...base, questions: [mcq({ options: [{ text: "only" }] })] });
    expect(tooFew.success).toBe(false);
  });

  it("requires questions when publishing and positive points", () => {
    expect(quizFormSchema.safeParse({ ...base, publish: true }).success).toBe(false);
    expect(quizFormSchema.safeParse({ ...base, questions: [mcq({ points: "0" })] }).success).toBe(false);
    expect(quizFormSchema.safeParse({ ...base, questions: [mcq({ points: "1.234" })] }).success).toBe(false);
  });

  it("rejects an invalid time limit", () => {
    expect(quizFormSchema.safeParse({ ...base, minutes: "0" }).success).toBe(false);
    expect(quizFormSchema.safeParse({ ...base, minutes: "601" }).success).toBe(false);
    expect(quizFormSchema.safeParse({ ...base, minutes: "30" }).success).toBe(true);
  });
});

describe("toPayload", () => {
  it("marks exactly the chosen multiple-choice option as correct", () => {
    const payload = toPayload({ ...base, minutes: "20", questions: [mcq()] });
    expect(payload.time_limit_minutes).toBe(20);
    expect(payload.questions[0]).toMatchObject({
      type: "mcq",
      points: 2,
      options: [
        { text: "3", is_correct: false },
        { text: "4", is_correct: true },
      ],
    });
  });

  it("builds fixed True/False options", () => {
    const tf = { ...newQuestion("true_false"), prompt: "Sky is blue", correctIndex: 1 };
    expect(toPayload({ ...base, questions: [tf] }).questions[0]?.options).toEqual([
      { text: "True", is_correct: false },
      { text: "False", is_correct: true },
    ]);
  });

  it("treats short-answer options as accepted answers and omits empty optional fields", () => {
    const short = { ...newQuestion("short_answer"), prompt: "Capital?", options: [{ text: "Paris" }] };
    const payload = toPayload({ ...base, questions: [short] });
    expect(payload.questions[0]?.options).toEqual([{ text: "Paris", is_correct: true }]);
    expect(payload).not.toHaveProperty("description");
    expect(payload).not.toHaveProperty("time_limit_minutes");
    expect(payload).not.toHaveProperty("due_at");
  });
});
import { describe, expect, it } from "vitest";

import { gradeFormSchema, submissionFormSchema } from "@/features/assignments/schemas";

describe("gradeFormSchema", () => {
  const schema = gradeFormSchema(50);

  it("accepts numbers from 0 to max_points with up to 2 decimals", () => {
    expect(schema.safeParse({ grade: "0", feedback: "" }).success).toBe(true);
    expect(schema.safeParse({ grade: "45.5", feedback: "" }).success).toBe(true);
    expect(schema.safeParse({ grade: "50", feedback: "" }).success).toBe(true);
  });

  it("rejects grades above the maximum, negatives, text and too many decimals", () => {
    for (const grade of ["51", "-1", "abc", "", "1.234"]) {
      expect(schema.safeParse({ grade, feedback: "" }).success, grade).toBe(false);
    }
  });
});

describe("submissionFormSchema", () => {
  it("needs an answer or at least one attachment", () => {
    expect(submissionFormSchema.safeParse({ content: "   ", attachments: [] }).success).toBe(false);
    expect(submissionFormSchema.safeParse({ content: "My answer", attachments: [] }).success).toBe(true);
    const file = { file_id: "6f9619ff-8b86-4011-b42d-00c04fc964ff", name: "a.pdf", mime_type: "application/pdf" };
    expect(submissionFormSchema.safeParse({ content: "", attachments: [file] }).success).toBe(true);
  });
});
Makefile
Recipe lines must start with a TAB character.
# NOTE: recipe lines must be indented with a TAB character, not spaces.

COMPOSE_TEST := docker compose -f docker-compose.test.yml
TEST_DB_URL  := postgresql+asyncpg://test:test@localhost:5433/educonnect_test
PYTHON       ?= python
ARGS         ?=

.PHONY: help install-dev up up-dev down logs seed seed-reset lint test test-fast test-cov test-local test-frontend test-db-up test-db-down

help:
	@echo "make up            build and start the whole stack (http://localhost:8080)"
	@echo "make up-dev        hot-reload stack (API :8000, Vite :5173)"
	@echo "make down          stop the stack (add -v via 'docker compose down -v' to delete data)"
	@echo "make logs          follow container logs"
	@echo "make seed          load demo data (admin, teachers, students, classrooms)"
	@echo "make seed-reset    delete the demo data and load it again"
	@echo "make lint          ruff (backend) + eslint (frontend)"
	@echo "make test          ephemeral Postgres + ALL backend tests"
	@echo "make test-fast     core backend suite only (-m core)"
	@echo "make test-cov      backend tests with a coverage report"
	@echo "make test-frontend vitest unit tests"
	@echo "make test-local    backend tests against the Postgres from docker-compose.yml"
	@echo "extra pytest args: make test ARGS='-k classroom -x'"

install-dev:
	cd backend && $(PYTHON) -m pip install -r requirements-dev.txt

up:
	docker compose up --build -d

up-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

seed:
	docker compose exec backend python -m scripts.seed

seed-reset:
	docker compose exec backend python -m scripts.seed --reset

lint:
	cd backend && ruff check .
	cd frontend && npm run lint

test-frontend:
	cd frontend && npm test

test-db-up:
	@$(COMPOSE_TEST) up -d --wait test-db

test-db-down:
	@$(COMPOSE_TEST) down -v

test: test-db-up
	@cd backend && TEST_DATABASE_URL="$(TEST_DB_URL)" $(PYTHON) -m pytest $(ARGS); \
	status=$$?; \
	cd .. && $(COMPOSE_TEST) down -v >/dev/null 2>&1; \
	exit $$status

test-fast:
	@$(MAKE) --no-print-directory test ARGS="-m core $(ARGS)"

test-cov:
	@$(MAKE) --no-print-directory test ARGS="--cov=app --cov-report=term-missing $(ARGS)"

test-local:
	cd backend && $(PYTHON) -m pytest $(ARGS)
GitHub Actions
name: CI

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  backend:
    name: Backend (lint, migrations, tests)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: educonnect_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U test -d educonnect_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      TEST_DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/educonnect_test
      DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/educonnect_test
      JWT_SECRET: ci-only-secret-ci-only-secret-ci-only-secret
      ENVIRONMENT: test
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/requirements*.txt

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Lint (ruff)
        run: ruff check .

      - name: Migrations apply, roll back and match the models
        run: |
          alembic upgrade head
          alembic downgrade base
          alembic upgrade head
          alembic check
          alembic downgrade base

      - name: Tests
        run: python -m pytest -q

  frontend:
    name: Frontend (lint, types, tests, build)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Lint (eslint)
        run: npm run lint

      - name: Type-check
        run: npm run typecheck

      - name: Unit tests (vitest)
        run: npm test

      - name: Build
        run: npm run build

  docker:
    name: Docker images build
    needs: [backend, frontend]
    runs-on: ubuntu-latest
    env:
      JWT_SECRET: ci-only-secret-ci-only-secret-ci-only-secret
    steps:
      - uses: actions/checkout@v4
      - name: Validate compose files
        run: |
          docker compose config -q
          docker compose -f docker-compose.yml -f docker-compose.dev.yml config -q
      - name: Build images
        run: docker compose build
README
# EduConnect

A Google Classroom-style learning platform: classes, announcements, assignments with grading,
auto-graded quizzes, materials, file uploads, a to-do list and live notifications.

**Stack:** FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Redis · JWT auth ·
React 18 · Vite · TypeScript · TanStack Query · Tailwind + shadcn/ui

## Architecture

```text
                          ┌────────────────────────────────────────┐
                          │ Browser: React SPA                     │
                          │ Router · TanStack Query · Zustand auth │
                          └───────┬───────────────────────┬────────┘
                static files      │ REST (Axios, JWT)     │ WebSocket
                      │           │ /api/v1/*             │ /ws/notifications
                      ▼           ▼                       ▼
             ┌────────────┐  ┌───────────────────────────────────────────┐
             │ nginx :8080│  │ FastAPI :8000 (uvicorn, one worker)       │
             │ (SPA build)│  │                                           │
             └────────────┘  │  routers → services → SQLAlchemy (async)  │
                             │     │          │                          │
                             │     │          ├─ notification push ──┐   │
                             │     │          │                      ▼   │
                             │     │          │            ConnectionManager
                             │     └─ deps: JWT, RBAC, classroom access   │
                             └──────┬───────────────┬─────────────┬──────┘
                                    │               │             │
                                    ▼               ▼             ▼
                             ┌────────────┐  ┌────────────┐  ┌───────────────┐
                             │ PostgreSQL │  │   Redis    │  │ File storage  │
                             │ users,     │  │ refresh    │  │ LocalStorage  │
                             │ classrooms,│  │ token      │  │ (S3-style     │
                             │ work, ...  │  │ revocation,│  │  interface)   │
                             └────────────┘  │ rate limits│  └───────────────┘
                                             └────────────┘
```

Request flow: a router validates input (Pydantic) and resolves access (dependencies), a service
holds the business rules and talks to the database, and responses are shaped by read schemas
(students never receive answer keys or other students' data).

## Quick start (Docker)

Requires Docker with Compose v2.24+.

```bash
cp .env.example .env
# set JWT_SECRET in .env:
python -c "import secrets; print(secrets.token_urlsafe(64))"

docker compose up --build -d      # or: make up
docker compose exec backend python -m scripts.seed      # optional demo data (or: make seed)
```

| What | URL |
|---|---|
| App | http://localhost:8080 |
| **API docs (Swagger UI)** | http://localhost:8000/docs |
| API docs (ReDoc) | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/api/v1/openapi.json |
| Health / readiness | http://localhost:8000/health · http://localhost:8000/health/ready |

Migrations are applied automatically when the backend container starts.
`/docs` and `/redoc` are disabled when `ENVIRONMENT=production`.

### Demo accounts

After `make seed`, every account uses the password **`Passw0rd!`** (change it with `SEED_PASSWORD`).

| Role | Email |
|---|---|
| admin | admin@example.com |
| teacher | rivera@example.com (owns *Algebra I*), chen@example.com (owns *Biology Basics*) |
| students | sam@, priya@, liam@, aisha@, noah@example.com |

Join codes: `ALGEBRA1`, `BIOLOGY1`. The seed includes published and draft assignments, returned,
graded and to-grade submissions, quizzes with attempts, materials, comments and notifications.
`make seed-reset` deletes the demo data and creates it again.

## Development

**Hot reload in Docker**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build   # or: make up-dev
# API http://localhost:8000   ·   Vite http://localhost:5173
```

**On your machine** (databases in Docker, code on the host)

```bash
docker compose up -d postgres redis

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # DATABASE_URL, JWT_SECRET, ...
alembic upgrade head
uvicorn app.main:app --reload     # keep ONE worker: WebSocket state is in-process

cd ../frontend
cp .env.example .env
npm install
npm run dev
```

## Tests and lint

```bash
make test            # all backend tests on an ephemeral PostgreSQL (port 5433, destroyed afterwards)
make test-fast       # core suite only
make test-cov        # with coverage
make test-frontend   # vitest unit tests
make lint            # ruff + eslint
```

CI (`.github/workflows/ci.yml`) runs on every push and pull request:
backend lint, migration upgrade/downgrade/drift check and tests against PostgreSQL;
frontend lint, type-check, unit tests and build; then a Docker image build.
Commit `frontend/package-lock.json`: CI and the Dockerfile use `npm ci`.

## Configuration

Docker Compose reads the root `.env`. For running the API on the host, use `backend/.env`.

| Variable | Default | Notes |
|---|---|---|
| `JWT_SECRET` | none, **required** | At least 32 characters |
| `ENVIRONMENT` | `development` | `production` hides the docs and the dev-only unauthenticated `/static/uploads` mount |
| `POSTGRES_PASSWORD` | `educonnect` | URL-safe characters only |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | `15` / `7` | |
| `CORS_ORIGINS` | `http://localhost:8080,http://localhost:5173` | Must include the frontend's origin |
| `VITE_API_URL` / `VITE_WS_URL` | `http://localhost:8000/api/v1` / `ws://localhost:8000` | Baked in at frontend **build** time |

## Project layout

```text
backend/app/   core (config, security, deps)  ·  db  ·  models  ·  schemas
               api/v1/routers  ·  services (business logic)  ·  websockets  ·  utils
backend/alembic/   migrations      backend/scripts/seed.py   demo data      backend/tests/
frontend/src/  api · components · features (per domain) · hooks · pages · routes · store · types
```

## Security notes

- Passwords are hashed with bcrypt; JWT access tokens last 15 minutes. Refresh tokens rotate on
  every use and are revoked in Redis (reuse is rejected).
- Roles are read from the database on every request. Classroom access is enforced per classroom
  (non-members get 404, so ids cannot be probed).
- Uploads are checked by extension **and** content, are size-limited, and are served only through
  the authenticated `GET /files/{id}`.
- Rate limits protect login, registration, joining and uploads.
- Tokens are kept in `localStorage`, so the SPA must stay free of `dangerouslySetInnerHTML` and
  untrusted third-party scripts.

## Production checklist

- `ENVIRONMENT=production`, a long random `JWT_SECRET`, a strong `POSTGRES_PASSWORD`.
- Put TLS in front (reverse proxy), set `CORS_ORIGINS` to the real origin, and rebuild the
  frontend with `VITE_API_URL=https://api.example.com/api/v1` and `VITE_WS_URL=wss://api.example.com`.
- Proxy `/ws/` with `Upgrade` headers and a read timeout above 90 s.
- Back up the `postgres_data` and `storage_data` volumes.

## Known limitations

- **One API worker.** The WebSocket connection registry is in memory. Scaling out needs Redis
  pub/sub in `websockets/notifier.py`.
- **No Celery worker yet.** Redis is used for token revocation and rate limiting only. Background
  jobs (email, file processing, and later TTS) are not wired in.
- Files uploaded and then abandoned in a form stay on disk until a cleanup job exists.
- Local file storage only (the storage interface is ready for S3/MinIO).

## Roadmap: Phase 2 (accessibility)

Neural text-to-speech and speech-to-text, voice commands such as "open file <name>", and spoken
feedback for visually impaired students. The frontend already has landmarks, a skip link,
labelled controls and live-region announcements as groundwork.

How to run and test
1. Frontend dependencies and lock file
cd frontend
npm install                    # picks up eslint, vitest and the new scripts; creates package-lock.json
npm run lint                   # may report a few existing issues; --fix handles most
npm run typecheck
npm test                       # about 25 unit tests
cd ..
2. Run the whole stack
cp .env.example .env
# edit .env and set JWT_SECRET (python -c "import secrets; print(secrets.token_urlsafe(64))")

docker compose down                    # stop the old STEP 1 stack if it is running
docker compose up --build -d
docker compose ps                      # postgres, redis, backend, frontend should become "healthy"
docker compose logs backend | head     # "Applying database migrations..." then uvicorn started

docker compose exec backend python -m scripts.seed
Open http://localhost:8080 and sign in as rivera@example.com / Passw0rd!. Swagger is at http://localhost:8000/docs.
3. Checks
#	Do this	Expected
1	docker compose up without JWT_SECRET	Fails at once with "Set JWT_SECRET in .env"
2	curl localhost:8000/health/ready	{"status":"ready","database":"up"}
3	Sign in as rivera@example.com	Algebra I, with a returned, a graded and a to-grade submission, plus a quiz with two attempts
4	Sign in as sam@example.com	Algebra I in Classes, to-do items, and an unread "material" notification
5	Sign in as liam@example.com	Both classes appear, because Liam is enrolled in both
6	make seed again	"Already seeded." and no changes
7	make seed-reset	The demo data is replaced, and the same accounts work
8	Join BIOLOGY1 as a fresh student	Joins as a student
9	docker compose restart backend	Comes back healthy. Migrations run again and change nothing
10	docker compose down, then up -d	Data persists (named volumes). down -v wipes it
11	make up-dev, edit a backend file or a .tsx file	The API reloads, and Vite hot-reloads at http://localhost:5173
12	make lint	Ruff and ESLint run. Fix what they report on the first run
13	make test, then make test-frontend	Backend suite passes, frontend unit tests pass
14	Push to GitHub, or open a pull request	Three CI jobs: backend, frontend, docker
Troubleshooting
Problem	Fix
ports must be a sequence or an unknown !override tag	Docker Compose is older than 2.24. Update it, or use only docker compose up and run the frontend with npm run dev
Backend restarts in a loop	docker compose logs backend. Common causes: missing JWT_SECRET, or POSTGRES_PASSWORD changed after the database volume was created (run docker compose down -v once)
sh: ... docker-entrypoint.sh: not found or \r errors	The script has Windows (CRLF) line endings. Re-checkout with .gitattributes in place, or run dos2unix backend/docker-entrypoint.sh
Browser shows CORS errors on localhost:8080	CORS_ORIGINS in .env must include http://localhost:8080
The frontend calls the wrong API URL	VITE_* values are baked in at build time. Change .env, then docker compose build frontend
npm ci fails during the frontend image build	package-lock.json is missing or out of date. Run npm install in frontend/ and commit the lock file
Login with admin@example.com returns 401	The seed has not run. make seed
duplicate key ... join_code while seeding	A non-demo classroom already uses ALGEBRA1 or BIOLOGY1. Change the codes in scripts/seed.py
CI fails at alembic check	The models and migrations disagree. The diff in the log says which column or index. Paste it here and I will fix the migration
CI fails at ruff check or npm run lint	Run ruff check --fix . in backend/ and npm run lint -- --fix in frontend/, then fix what remains
make says missing separator	Recipe lines need a TAB, not spaces
The planned 18 steps are complete. The remaining work is listed under "Known limitations" and "Roadmap" in the README. The two main items are Celery workers and the Phase 2 accessibility features. Reply NEXT to start Phase 2.
```