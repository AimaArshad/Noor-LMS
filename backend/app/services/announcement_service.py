"""Announcement business logic. Every method is scoped to one classroom."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Announcement, Classroom, User
from app.schemas.announcements import AnnouncementCreate, AnnouncementRead, AnnouncementUpdate
from app.schemas.common import Page
from app.services.guards import ensure_not_archived


class AnnouncementService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    @staticmethod
    def _select() -> Select[tuple[Announcement]]:
        """Base query with the author eager-loaded (lazy loads fail under AsyncSession)."""
        return select(Announcement).options(joinedload(Announcement.author))

    async def get(
        self, classroom_id: uuid.UUID, announcement_id: uuid.UUID, *, refresh: bool = False
    ) -> Announcement:
        """Return an announcement of ``classroom_id``.

        Args:
            refresh: Reload column values from the DB (use after a commit to pick up
                server-generated ``created_at`` / ``updated_at``).

        Raises:
            HTTPException: 404 when it does not exist in this classroom.
        """
        stmt = self._select().where(
            Announcement.id == announcement_id, Announcement.classroom_id == classroom_id
        )
        if refresh:
            stmt = stmt.execution_options(populate_existing=True)
        announcement = await self.db.scalar(stmt)
        if announcement is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found")
        return announcement

    async def list_for_classroom(
        self, classroom_id: uuid.UUID, *, limit: int, offset: int
    ) -> Page[AnnouncementRead]:
        """Newest-first page of the classroom stream."""
        total = (
            await self.db.scalar(
                select(func.count())
                .select_from(Announcement)
                .where(Announcement.classroom_id == classroom_id)
            )
            or 0
        )
        stmt = (
            self._select()
            .where(Announcement.classroom_id == classroom_id)
            .order_by(Announcement.created_at.desc(), Announcement.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.scalars(stmt)).all()
        return Page[AnnouncementRead](
            items=[AnnouncementRead.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #
    async def create(
        self, classroom: Classroom, author: User, data: AnnouncementCreate
    ) -> Announcement:
        """Post an announcement as ``author``.

        Raises:
            HTTPException: 403 when the classroom is archived.
        """
        ensure_not_archived(classroom.is_archived)
        announcement = Announcement(
            classroom_id=classroom.id, author_id=author.id, content=data.content
        )
        self.db.add(announcement)
        await self.db.commit()
        return await self.get(classroom.id, announcement.id, refresh=True)

    async def update(
        self, classroom: Classroom, announcement: Announcement, data: AnnouncementUpdate
    ) -> Announcement:
        """Apply a PATCH body (only the fields the client sent)."""
        ensure_not_archived(classroom.is_archived)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(announcement, field, value)
        await self.db.commit()
        return await self.get(classroom.id, announcement.id, refresh=True)

    async def delete(self, classroom: Classroom, announcement: Announcement) -> None:
        """Delete an announcement.

        Deleted through the ORM on purpose: the ``after_delete`` listener in
        ``models/comment.py`` removes its (FK-less) comments.
        """
        ensure_not_archived(classroom.is_archived)
        await self.db.delete(announcement)
        await self.db.commit()