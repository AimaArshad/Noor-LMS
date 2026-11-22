"""Audiobook REST endpoints.

Mounted twice in api.py:
  prefix /classrooms/{classroom_id}/audiobooks   → classroom_router
  prefix /audiobooks                             → audiobook_router
"""

# from __future__ import annotations

import asyncio
import os
import pathlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.classroom_deps import ClassroomTeacherAccess
from app.core.deps import CurrentUser
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import User
from app.schemas.audiobooks import (
    AudiobookCreate,
    AudiobookListItem,
    AudiobookManifest,
    AudiobookRead,
    PlaybackProgressRead,
    PlaybackProgressUpdate,
    SearchHit,
)
from app.schemas.common import Message
from app.services.audiobook_service import AudiobookService

# ---------------------------------------------------------------------------
# Sub-routers
# ---------------------------------------------------------------------------

classroom_router = APIRouter()   # mounted at /classrooms/{classroom_id}/audiobooks
audiobook_router = APIRouter()   # mounted at /audiobooks

AUDIO_RATE_LIMIT = "600/minute"  # higher — only cached file serving


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def get_audiobook_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AudiobookService:
    return AudiobookService(db)


Service = Annotated[AudiobookService, Depends(get_audiobook_service)]

_404 = {404: {"model": Message}}
_403 = {403: {"model": Message}}


# ---------------------------------------------------------------------------
# Classroom-scoped creation endpoint
# ---------------------------------------------------------------------------


@classroom_router.post(
    "",
    response_model=AudiobookRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an audiobook from a file (classroom teacher)",
    responses={**_403, **_404, 422: {"model": Message}},
)
async def create_audiobook(
    body: AudiobookCreate,
    access: ClassroomTeacherAccess,
    service: Service,
) -> AudiobookRead:
    """Upload a PDF/DOCX/TXT and start building its audiobook.

    * File must have been uploaded by the teacher.
    * Archived classrooms return 403.
    * If an audiobook for this classroom+file already exists, that row is returned.
    """
    ab = await service.create(access.classroom, access.user, body)
    return AudiobookRead.model_validate(ab)


# ---------------------------------------------------------------------------
# Audiobook-level: rebuild + delete
# ---------------------------------------------------------------------------


@audiobook_router.post(
    "/{audiobook_id}/rebuild",
    response_model=AudiobookRead,
    summary="Re-queue an audiobook build (teacher)",
    responses={**_403, **_404, 409: {"model": Message}},
)
async def rebuild_audiobook(
    audiobook_id: uuid.UUID,
    user: CurrentUser,
    service: Service,
) -> AudiobookRead:
    ab = await service.rebuild(audiobook_id, user)
    return AudiobookRead.model_validate(ab)


@audiobook_router.delete(
    "/{audiobook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an audiobook and its cached audio (teacher)",
    responses={**_403, **_404},
)
async def delete_audiobook(
    audiobook_id: uuid.UUID,
    user: CurrentUser,
    service: Service,
) -> Response:
    await service.delete(audiobook_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Read: list (across classrooms)
# ---------------------------------------------------------------------------


@audiobook_router.get(
    "",
    response_model=list[AudiobookListItem],
    summary="List all audiobooks accessible to the caller",
)
async def list_audiobooks(
    user: CurrentUser,
    service: Service,
    q: Annotated[str | None, Query(description="Fuzzy title filter")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> list[AudiobookListItem]:
    return await service.list_accessible(user, q=q, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@audiobook_router.get(
    "/{audiobook_id}/manifest",
    response_model=AudiobookManifest,
    summary="Outline + segment list + progress (player manifest)",
    responses={**_404},
)
async def get_manifest(
    audiobook_id: uuid.UUID,
    user: CurrentUser,
    service: Service,
) -> AudiobookManifest:
    return await service.get_manifest(audiobook_id, user)


# ---------------------------------------------------------------------------
# Segment audio
# ---------------------------------------------------------------------------


@audiobook_router.get(
    "/{audiobook_id}/segments/{seq}/audio",
    summary="Stream cached segment MP3",
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio bytes"},
        404: {"description": "not_found or not_ready (see JSON body code)"},
    },
)
@limiter.limit(AUDIO_RATE_LIMIT)
async def get_segment_audio(
    request: Request,
    audiobook_id: uuid.UUID,
    seq: int,
    user: CurrentUser,
    service: Service,
    response: Response,
) -> Response:
    """Return the MP3 audio for a segment, with Range support.

    * Returns `Cache-Control: private, max-age=86400` (not `no-store`).
    * Returns JSON `{"code": "not_ready"}` with 404 when audio isn't synthesised yet.
    * Returns JSON `{"code": "not_found"}` with 404 when segment doesn't exist.
    """
    path: pathlib.Path = await service.get_segment_audio_path(audiobook_id, seq, user)

    file_size = path.stat().st_size

    # Cache-Control must override the global `no-store` default
    cache_control = "private, max-age=86400"

    # --- Range support ---
    range_header = request.headers.get("range")
    if range_header and range_header.startswith("bytes="):
        try:
            rng = range_header[6:]
            start_s, end_s = rng.split("-", 1)
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else file_size - 1
        except ValueError:
            start, end = 0, file_size - 1

        start = max(0, start)
        end = min(end, file_size - 1)
        length = end - start + 1

        def _iter_range():
            with open(path, "rb") as fh:
                fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(65536, remaining))
                    if not chunk:
                        break
                    yield chunk
                    remaining -= len(chunk)

        return StreamingResponse(
            _iter_range(),
            status_code=206,
            media_type="audio/mpeg",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(length),
                "Accept-Ranges": "bytes",
                "Cache-Control": cache_control,
            },
        )

    # --- Full file ---
    def _iter_full():
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        _iter_full(),
        status_code=200,
        media_type="audio/mpeg",
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Cache-Control": cache_control,
        },
    )


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


@audiobook_router.get(
    "/{audiobook_id}/progress",
    response_model=PlaybackProgressRead | None,
    summary="Get playback position",
    responses={**_404},
)
async def get_progress(
    audiobook_id: uuid.UUID,
    user: CurrentUser,
    service: Service,
) -> PlaybackProgressRead | None:
    return await service.get_progress(audiobook_id, user)


@audiobook_router.put(
    "/{audiobook_id}/progress",
    response_model=PlaybackProgressRead,
    summary="Upsert playback position",
    responses={**_404},
)
async def upsert_progress(
    audiobook_id: uuid.UUID,
    body: PlaybackProgressUpdate,
    user: CurrentUser,
    service: Service,
) -> PlaybackProgressRead:
    return await service.upsert_progress(audiobook_id, user, body)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@audiobook_router.get(
    "/{audiobook_id}/search",
    response_model=list[SearchHit],
    summary="Search within an audiobook (section titles + segment text)",
    responses={**_404},
)
async def search_audiobook(
    audiobook_id: uuid.UUID,
    user: CurrentUser,
    service: Service,
    q: Annotated[str, Query(min_length=1, max_length=200)] ,
) -> list[SearchHit]:
    return await service.search(audiobook_id, user, q)

