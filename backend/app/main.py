"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.errors import error_response, register_exception_handlers
from app.core.logging_config import setup_logging
from app.core.middleware import (
    ErrorBoundaryMiddleware,
    MaxBodySizeMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.openapi import API_DESCRIPTION, COMMON_RESPONSES, OPENAPI_TAGS
from app.core.rate_limit import limiter
from app.core.redis import close_redis
from app.db.session import engine, get_db
from app.websockets.manager import manager as ws_manager
from app.websockets.routes import router as ws_router

setup_logging(level="DEBUG" if settings.DEBUG else settings.LOG_LEVEL, json_logs=settings.json_logs)
logger = logging.getLogger("educonnect")

# multipart boundaries + form field headers on top of the file itself
_MULTIPART_OVERHEAD_BYTES = 64 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hooks."""
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Starting %s v%s [%s]", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)
    yield
    await ws_manager.close_all()
    await close_redis()
    await engine.dispose()
    logger.info("Database engine disposed. Shutdown complete.")


def create_app() -> FastAPI:
    """Application factory."""
    docs_enabled = not settings.is_production
    docs_paths = (
        {"/docs", "/redoc", "/docs/oauth2-redirect", f"{settings.API_V1_PREFIX}/openapi.json"}
        if docs_enabled
        else set()
    )

    app = FastAPI(
        title=f"{settings.PROJECT_NAME} API",
        version=settings.VERSION,
        summary="Google Classroom-style learning platform API.",
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        # In production neither the docs nor the schema are published.
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if docs_enabled else None,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        swagger_ui_parameters={"persistAuthorization": True, "displayRequestDuration": True},
        lifespan=lifespan,
    )

    # ---- Rate limiting + error envelope ----
    app.state.limiter = limiter
    register_exception_handlers(app)

    # Middleware: the LAST one added is the OUTERMOST. Resulting order, outermost first:
    # RequestContext -> SecurityHeaders -> CORS -> ErrorBoundary -> MaxBodySize -> SlowAPI -> app
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_bytes=settings.max_upload_size_bytes + _MULTIPART_OVERHEAD_BYTES,
        path=f"{settings.API_V1_PREFIX}/files/upload",
    )
    app.add_middleware(ErrorBoundaryMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Range", "X-Request-ID"],
        expose_headers=[
            "Content-Range",
            "Content-Disposition",
            "Accept-Ranges",
            "Date",
            "X-Request-ID",
            "X-Total-Count",
        ],
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts=settings.is_production,
        files_prefix=f"{settings.API_V1_PREFIX}/files/",
        relaxed_csp_paths=docs_paths,
    )
    app.add_middleware(RequestContextMiddleware)

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
            return error_response(
                503,
                "Database unavailable",
                code="service_unavailable",
                details={"database": "down"},
            )
        return JSONResponse(content={"status": "ready", "database": "up"})

    # ---- API v1 ----
    app.include_router(api_router, prefix=settings.API_V1_PREFIX, responses=COMMON_RESPONSES)
    app.include_router(ws_router)  # serves /ws/notifications (outside /api/v1)

    # ---- DEV ONLY: raw static access to stored files ----
    # WARNING: this bypasses authentication. Never enabled outside development;
    # the real download path is the authenticated GET /api/v1/files/{id}.
    if settings.ENVIRONMENT == "development":
        settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        app.mount("/static/uploads", StaticFiles(directory=settings.STORAGE_DIR), name="dev-uploads")
        logger.warning(
            "DEV ONLY: %s is served unauthenticated at /static/uploads", settings.STORAGE_DIR
        )

    return app


app = create_app()
