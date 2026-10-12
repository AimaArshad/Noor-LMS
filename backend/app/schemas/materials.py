"""Material schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import (
    AttachmentList,
    AttachmentRef,
    ORMModel,
    OptBody10k,
    RequestModel,
    Str255,
    UpdateModel,
)


class MaterialCreate(RequestModel):
    title: Str255
    description: OptBody10k = None
    attachments: AttachmentList = Field(default_factory=list)


class MaterialUpdate(UpdateModel):
    non_nullable = frozenset({"title", "attachments"})

    title: Str255 | None = None
    description: OptBody10k = None
    attachments: AttachmentList | None = None


class MaterialRead(ORMModel):
    id: uuid.UUID
    classroom_id: uuid.UUID
    title: str
    description: str | None = None
    attachments: list[AttachmentRef] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime