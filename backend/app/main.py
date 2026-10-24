"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import engine, get_db

# add with the other imports
from app.core.redis import close_redis

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("educonnect")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hooks."""
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Starting %s v%s [%s]", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)
    # in lifespan(), after `yield`: to close redis on shutdown
    yield
    await close_redis()          # ← add this line
    await engine.dispose()
    logger.info("Database engine disposed. Shutdown complete.")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=f"{settings.PROJECT_NAME} API",
        version=settings.VERSION,
        description="Google Classroom-style learning platform API.",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        lifespan=lifespan,
    )

    # ---- Rate limiting ----
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    # ---- CORS ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    # ---- Global error handler (never leak internals) ----
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # ---- Health ----
    @app.get("/health", tags=["meta"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        """Return basic liveness information (no dependencies checked)."""
        return {
            "status": "ok",
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        }

    @app.get("/health/ready", tags=["meta"], summary="Readiness probe")
    async def readiness(db: AsyncSession = Depends(get_db)) -> JSONResponse:
        """Verify the database connection is usable. Returns 503 on failure."""
        try:
            await db.execute(text("SELECT 1"))
        except Exception:
            logger.exception("Readiness check failed")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unavailable", "database": "down"},
            )
        return JSONResponse(content={"status": "ready", "database": "up"})

    # ---- API v1 ----
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()