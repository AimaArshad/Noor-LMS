"""Notification schemas (REST and WebSocket payloads)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import (
    ORMModel,
    OptBody5k,
    OptUrlOrPath,
    Page,
    RequestModel,
    Str255,
)


class NotificationCreate(RequestModel):
    """Internal DTO: services create notifications; clients never post them."""

    user_id: uuid.UUID
    title: Str255
    body: OptBody5k = None
    type: str = Field(default="general", min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    link: OptUrlOrPath = None


class NotificationUpdate(RequestModel):
    """Reserved: marking a notification read/unread. Defaults to ``is_read=true``."""

    is_read: bool = True


class NotificationRead(ORMModel):
    """Same shape over REST and in WebSocket ``notification`` messages."""

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    body: str | None = None
    type: str
    link: str | None = None
    is_read: bool
    created_at: datetime


class NotificationPage(Page[NotificationRead]):
    """Paginated notifications plus the unread counter for the bell icon."""

    unread_count: int = Field(default=0, ge=0)


class UnreadCount(BaseModel):
    """Response of ``GET /notifications/unread-count``."""

    unread_count: int = Field(ge=0)


class ReadAllResult(BaseModel):
    """Response of ``POST /notifications/read-all``."""

    updated: int = Field(ge=0)
