"""Notification business logic and post-commit WebSocket push.

Services create notifications with :func:`stage_notification` /
:func:`stage_notifications`::

    stage_notification(db, user_id=teacher_id, title="Sam turned in HW 1",
                       type="submission_turned_in", link="/classrooms/...")
    await db.commit()          # <- the live push happens here, only if the commit succeeds

The row is written in the caller's transaction. The WebSocket payload is queued on the
session and delivered by the ``after_commit`` hook below, so a rolled-back request
never produces a ghost notification on somebody's screen.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import event, func, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models import Notification
from app.schemas.notifications import NotificationPage, NotificationRead
from app.websockets.notifier import push_notification

logger = logging.getLogger("educonnect.notifications")

_PENDING_KEY = "ws_pending_notifications"
_background_tasks: set[asyncio.Task[None]] = set()  # strong refs so tasks are not garbage-collected


def _clip(text: str, limit: int = 255) -> str:
    """Notification.title is VARCHAR(255)."""
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ====================================================================== #
# Staging + post-commit push
# ====================================================================== #
def stage_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str,
    body: str | None = None,
    type: str = "general",  # noqa: A002 - mirrors the column name
    link: str | None = None,
) -> Notification:
    """Add a notification to ``db`` and queue its live push for after the commit.

    ``id`` and ``created_at`` are set here (not by the database) so the WebSocket payload
    is complete before the row is flushed.
    """
    notification = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        title=_clip(title),
        body=body,
        type=type,
        link=link,
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(notification)
    payload = NotificationRead.model_validate(notification).model_dump(mode="json")
    db.sync_session.info.setdefault(_PENDING_KEY, []).append((notification, user_id, payload))
    return notification


def stage_notifications(
    db: AsyncSession,
    user_ids: Iterable[uuid.UUID],
    *,
    title: str,
    body: str | None = None,
    type: str = "general",  # noqa: A002
    link: str | None = None,
) -> int:
    """:func:`stage_notification` for many users. Returns how many were staged."""
    count = 0
    for user_id in user_ids:
        stage_notification(db, user_id=user_id, title=title, body=body, type=type, link=link)
        count += 1
    return count


async def _deliver(deliveries: list[tuple[uuid.UUID, dict[str, Any]]]) -> None:
    await asyncio.gather(*(push_notification(uid, payload) for uid, payload in deliveries))


@event.listens_for(Session, "after_commit")
def _push_after_commit(session: Session) -> None:
    """Deliver queued pushes once the transaction is really committed.

    Entries whose notification is not persistent (rolled back / expunged) are dropped.
    """
    pending = session.info.pop(_PENDING_KEY, None)
    if not pending:
        return
    deliveries = [(uid, payload) for obj, uid, payload in pending if inspect(obj).persistent]
    if not deliveries:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # sync session outside an event loop (scripts): nothing to push to
        return
    task = loop.create_task(_deliver(deliveries))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


# ====================================================================== #
# REST logic
# ====================================================================== #
class NotificationService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def unread_count(self, user_id: uuid.UUID) -> int:
        return (
            await self.db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            )
            or 0
        )

    async def list_for_user(
        self, user_id: uuid.UUID, *, unread_only: bool, limit: int, offset: int
    ) -> NotificationPage:
        """Newest-first page of the user's notifications (``unread_count`` ignores the filter)."""
        conditions: list[Any] = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.is_read.is_(False))

        total = (
            await self.db.scalar(select(func.count()).select_from(Notification).where(*conditions))
            or 0
        )
        rows = (
            await self.db.scalars(
                select(Notification)
                .where(*conditions)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return NotificationPage(
            items=[NotificationRead.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
            unread_count=await self.unread_count(user_id),
        )

    async def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
        """Mark one of the caller's notifications read (idempotent).

        Raises:
            HTTPException: 404 when it does not exist or belongs to somebody else.
        """
        notification = await self.db.scalar(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        )
        if notification is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
        if not notification.is_read:
            notification.is_read = True
            await self.db.commit()
        return notification

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        """Mark every unread notification of the user read; return how many changed."""
        result = await self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
            .execution_options(synchronize_session=False)
        )
        await self.db.commit()
        return result.rowcount or 0  # type: ignore[attr-defined]