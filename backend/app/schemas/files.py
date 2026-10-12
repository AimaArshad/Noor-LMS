"""File metadata schemas.

``stored_name`` and ``path`` are internal storage details and are never returned
to clients.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StringConstraints

from app.schemas.common import ORMModel, RequestModel, Str255, UpdateModel

_MIME_PATTERN = r"^[\w.+-]+/[\w.+-]+$"


def _safe_filename(value: str) -> str:
    """Drop any directory part and control characters; reject empty / dot names."""
    value = value.replace("\x00", "").replace("\\", "/").split("/")[-1].strip()
    if not value or value in {".", ".."}:
        raise ValueError("Invalid file name")
    return value


SafeFilename = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
    AfterValidator(_safe_filename),
]


class FileCreate(RequestModel):
    """Internal DTO used by the storage service after a successful upload."""

    uploader_id: uuid.UUID | None = None
    original_name: SafeFilename
    stored_name: Str255
    mime_type: str = Field(pattern=_MIME_PATTERN, max_length=255)
    size_bytes: int = Field(ge=0)
    path: str = Field(min_length=1, max_length=1024)
    storage_backend: Literal["local", "s3"] = "local"


class FileUpdate(UpdateModel):
    """Rename the display name of a file."""

    non_nullable = frozenset({"original_name"})

    original_name: SafeFilename | None = None


class FileRead(ORMModel):
    id: uuid.UUID
    uploader_id: uuid.UUID | None = None
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime