"""Announcement schemas."""

import uuid
from datetime import datetime

from app.schemas.common import Body10k, ORMModel, RequestModel, UpdateModel
from app.schemas.users import UserPublic


class AnnouncementCreate(RequestModel):
    content: Body10k


class AnnouncementUpdate(UpdateModel):
    non_nullable = frozenset({"content"})

    content: Body10k | None = None


class AnnouncementRead(ORMModel):
    """``author`` requires ``Announcement.author`` to be eager-loaded (or leave it None)."""

    id: uuid.UUID
    classroom_id: uuid.UUID
    author_id: uuid.UUID | None = None
    author: UserPublic | None = None
    content: str
    created_at: datetime
    updated_at: datetime