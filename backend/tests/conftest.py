"""Shared fixtures: isolated test DB, in-memory fake Redis, ASGI test client."""

import os
from sqlalchemy import text

# Must run BEFORE any `app.*` import. The DATABASE_URL is forced (not setdefault) so tests
# can never touch your dev database.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://educonnect:educonnect@localhost:5432/educonnect_test",
)
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-1234567890")
os.environ["RATE_LIMIT_DEFAULT"] = "100000/minute"
os.environ["RATE_LIMIT_STORAGE_URI"] = "memory://"


import tempfile
_TMP = tempfile.mkdtemp(prefix="educonnect_test_")
os.environ["STORAGE_DIR"] = os.path.join(_TMP, "storage")
os.environ["TTS_CACHE_DIR"] = os.path.join(_TMP, "tts_cache")
os.environ["AUDIOBOOK_AUDIO_DIR"] = os.path.join(_TMP, "audiobooks")

from collections.abc import AsyncIterator  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.rate_limit import limiter  # noqa: E402
from app.core.redis import get_redis  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


class FakeRedis:
    """Minimal in-memory stand-in for the Redis calls used by the auth module."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):  # noqa: ANN201
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def aclose(self) -> None:
        return None


@pytest_asyncio.fixture
async def engine():  # noqa: ANN201
    """Fresh schema per test, dropped afterwards."""
    eng = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()




@pytest_asyncio.fixture
async def session_maker(engine):  # noqa: ANN001, ANN201
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest_asyncio.fixture
async def client(session_maker, fake_redis) -> AsyncIterator[AsyncClient]:  # noqa: ANN001
    async def _get_db():  # noqa: ANN202
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = lambda: fake_redis
    limiter.enabled = False
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    limiter.enabled = True