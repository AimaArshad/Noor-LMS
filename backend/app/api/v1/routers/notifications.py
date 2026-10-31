"""Notification endpoints (live delivery: WebSocket /ws/notifications).

GET   /notifications                  list, newest first (?unread_only=true)
GET   /notifications/unread-count     number for the bell icon
PATCH /notifications/{id}/read        mark one read
POST  /notifications/read-all         mark all read
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.db.session import get_db
from app.schemas.common import Message
from app.schemas.notifications import (
    NotificationPage,
    NotificationRead,
    ReadAllResult,
    UnreadCount,
)
from app.services.notification_service import NotificationService

router = APIRouter()


def get_notification_service(db: Annotated[AsyncSession, Depends(get_db)]) -> NotificationService:
    """Build the per-request service (shares the request's DB session)."""
    return NotificationService(db)


Service = Annotated[NotificationService, Depends(get_notification_service)]


@router.get("", response_model=NotificationPage, summary="My notifications (newest first)")
async def list_notifications(
    user: CurrentUser,
    service: Service,
    unread_only: Annotated[bool, Query(description="Only unread notifications")] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationPage:
    return await service.list_for_user(user.id, unread_only=unread_only, limit=limit, offset=offset)


@router.get("/unread-count", response_model=UnreadCount, summary="Number of unread notifications")
async def unread_count(user: CurrentUser, service: Service) -> UnreadCount:
    return UnreadCount(unread_count=await service.unread_count(user.id))


@router.post("/read-all", response_model=ReadAllResult, summary="Mark all my notifications read")
async def read_all(user: CurrentUser, service: Service) -> ReadAllResult:
    return ReadAllResult(updated=await service.mark_all_read(user.id))


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark one notification read",
    responses={404: {"model": Message, "description": "Not found, or not yours"}},
)
async def mark_read(
    notification_id: uuid.UUID, user: CurrentUser, service: Service
) -> NotificationRead:
    """Idempotent: marking an already-read notification returns 200."""
    notification = await service.mark_read(user.id, notification_id)
    return NotificationRead.model_validate(notification)