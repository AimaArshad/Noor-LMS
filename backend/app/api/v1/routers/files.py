"""File endpoints.

POST   /files/upload   multipart upload (any authenticated user)
GET    /files/{id}     stream a file (access rules: see FileService.can_access)
DELETE /files/{id}     delete (uploader only, and only when not attached anywhere)
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, status
from fastapi import File as FileField
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.common import Message
from app.schemas.files import FileRead
from app.services.file_service import FileService
from app.services.storage import StorageBackend, get_storage
from app.utils.file_types import ALLOWED_EXTENSIONS, TYPE_BY_MIME
from app.utils.http import RangeNotSatisfiable, content_disposition, parse_range

logger = logging.getLogger("educonnect.files")

router = APIRouter()


def get_storage_backend() -> StorageBackend:
    """Backend used for new uploads (override in tests / switch to S3 here later)."""
    return get_storage("local")


def get_file_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
) -> FileService:
    return FileService(db, storage)


Service = Annotated[FileService, Depends(get_file_service)]


@router.post(
    "/upload",
    response_model=FileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file",
    description=(
        f"Multipart upload, field name `file`, max {settings.MAX_UPLOAD_SIZE_MB} MB.\n\n"
        f"Allowed extensions: `{'`, `'.join(ALLOWED_EXTENSIONS)}`. "
        "The content must match the extension; the client `Content-Type` is ignored."
    ),
    responses={
        400: {"model": Message, "description": "Empty file or missing file name"},
        413: {"model": Message, "description": "File too large"},
        415: {"model": Message, "description": "Type not allowed / content mismatch"},
    },
)
@limiter.limit("30/minute")
async def upload_file(
    request: Request,
    user: CurrentUser,
    service: Service,
    file: Annotated[UploadFile, FileField(description="The file to upload")],
) -> FileRead:
    stored = await service.upload(user, file)
    return FileRead.model_validate(stored)


@router.get(
    "/{file_id}",
    summary="Download / stream a file",
    response_class=StreamingResponse,
    responses={
        200: {"description": "File content", "content": {"application/octet-stream": {}}},
        206: {"description": "Partial content (Range request)"},
        404: {"model": Message, "description": "Not found, or you may not access it"},
        416: {"description": "Range not satisfiable"},
    },
)
async def download_file(
    request: Request,
    file_id: uuid.UUID,
    user: CurrentUser,
    service: Service,
    download: Annotated[bool, Query(description="Force a download instead of inline display")] = False,
) -> Response:
    file = await service.get_accessible(user, file_id)
    storage = service.backend_for(file)

    if not await storage.exists(file.path):
        logger.error("File %s is in the database but missing from storage (%s)", file.id, file.path)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File content not found")

    size = file.size_bytes
    try:
        byte_range = parse_range(request.headers.get("range"), size)
    except RangeNotSatisfiable:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    file_type = TYPE_BY_MIME.get(file.mime_type)
    inline = bool(file_type and file_type.inline_safe) and not download
    headers = {
        "Content-Disposition": content_disposition(file.original_name, inline=inline),
        "Accept-Ranges": "bytes",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600",
    }

    if byte_range is None:
        status_code, start, end = status.HTTP_200_OK, 0, None
        headers["Content-Length"] = str(size)
    else:
        start, end = byte_range
        status_code = status.HTTP_206_PARTIAL_CONTENT
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        headers["Content-Length"] = str(end - start + 1)

    return StreamingResponse(
        storage.open(file.path, start=start, end=end),
        status_code=status_code,
        media_type=file.mime_type,
        headers=headers,
    )


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a file (uploader only)",
    responses={
        403: {"model": Message, "description": "You are not the uploader"},
        404: {"model": Message},
        409: {"model": Message, "description": "File is still attached to classroom content"},
    },
)
async def delete_file(file_id: uuid.UUID, user: CurrentUser, service: Service) -> Response:
    await service.delete(user, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)