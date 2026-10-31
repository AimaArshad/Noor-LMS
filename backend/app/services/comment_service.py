"""Comment business logic for assignments and announcements (polymorphic target)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import (
    Announcement,
    Assignment,
    AssignmentState,
    Classroom,
    ClassroomMember,
    Comment,
    CommentTarget,
    MemberRole,
    User,
    UserRole,
)
from app.schemas.comments import CommentCreate, CommentRead
from app.schemas.common import Page
from app.services.guards import ensure_not_archived


@dataclass(frozen=True, slots=True)
class TargetAccess:
    """What the caller may do around a comment target."""

    classroom_id: uuid.UUID
    is_teacher: bool  # classroom teacher, or an admin who is not a member
    is_archived: bool


class CommentService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Target resolution + access
    # ------------------------------------------------------------------ #
    async def resolve_target(
        self,
        user: User,
        target_type: CommentTarget,
        target_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> TargetAccess | None:
        """Find the target's classroom and the caller's rights in it.

        Returns ``None`` (callers answer 404) when the target does not exist, the
        caller is not a member of its classroom (admins are exempt), or the target
        is a draft assignment and the caller is not a teacher.

        Args:
            lock: Take a ``FOR SHARE`` lock on the target row so a concurrent delete
                waits until our comment is committed (and then removes it).
        """
        if target_type == CommentTarget.ASSIGNMENT:
            stmt = select(Assignment.classroom_id, Assignment.state).where(
                Assignment.id == target_id
            )
        else:
            stmt = select(Announcement.classroom_id).where(Announcement.id == target_id)
        if lock:
            stmt = stmt.with_for_update(read=True)

        target = (await self.db.execute(stmt)).first()
        if target is None:
            return None
        classroom_id: uuid.UUID = target.classroom_id
        visible_to_students = (
            target_type != CommentTarget.ASSIGNMENT or target.state == AssignmentState.PUBLISHED
        )

        membership = (
            await self.db.execute(
                select(Classroom.is_archived, ClassroomMember.role)
                .select_from(Classroom)
                .outerjoin(
                    ClassroomMember,
                    and_(
                        ClassroomMember.classroom_id == Classroom.id,
                        ClassroomMember.user_id == user.id,
                    ),
                )
                .where(Classroom.id == classroom_id)
            )
        ).first()
        if membership is None:
            return None

        # Same rule as classroom_deps: members use their classroom role,
        # admins who are not members count as teachers.
        if membership.role is None:
            if user.role != UserRole.ADMIN:
                return None
            is_teacher = True
        else:
            is_teacher = membership.role == MemberRole.TEACHER

        if not visible_to_students and not is_teacher:
            return None
        return TargetAccess(
            classroom_id=classroom_id, is_teacher=is_teacher, is_archived=membership.is_archived
        )

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    async def _load(self, comment_id: uuid.UUID) -> Comment:
        """Reload a comment with its author and server-generated columns."""
        stmt = (
            select(Comment)
            .options(joinedload(Comment.author))
            .where(Comment.id == comment_id)
            .execution_options(populate_existing=True)
        )
        comment = await self.db.scalar(stmt)
        if comment is None:  # pragma: no cover - we just inserted it
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
        return comment

    async def list_for_target(
        self,
        user: User,
        target_type: CommentTarget,
        target_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> Page[CommentRead]:
        """Oldest-first comments of one target.

        Raises:
            HTTPException: 404 when the target is missing or not accessible.
        """
        if await self.resolve_target(user, target_type, target_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment target not found")

        where = (Comment.target_type == target_type, Comment.target_id == target_id)
        total = (
            await self.db.scalar(select(func.count()).select_from(Comment).where(*where)) or 0
        )
        stmt = (
            select(Comment)
            .options(joinedload(Comment.author))
            .where(*where)
            .order_by(Comment.created_at, Comment.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.scalars(stmt)).all()
        return Page[CommentRead](
            items=[CommentRead.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #
    async def create(self, user: User, data: CommentCreate) -> Comment:
        """Add a comment to an assignment or announcement.

        Raises:
            HTTPException: 404 target missing/inaccessible, 403 classroom archived.
        """
        target = await self.resolve_target(user, data.target_type, data.target_id, lock=True)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment target not found")
        ensure_not_archived(target.is_archived)

        comment = Comment(
            author_id=user.id,
            target_type=data.target_type,
            target_id=data.target_id,
            body=data.body,
        )
        self.db.add(comment)
        await self.db.commit()
        return await self._load(comment.id)

    async def delete(self, user: User, comment_id: uuid.UUID) -> None:
        """Delete a comment (its author, or a classroom teacher / admin).

        Raises:
            HTTPException: 404 unknown or inaccessible, 403 not allowed, 403 archived.
        """
        not_found = HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
        comment = await self.db.get(Comment, comment_id)
        if comment is None:
            raise not_found
        target = await self.resolve_target(user, comment.target_type, comment.target_id)
        if target is None:
            raise not_found
        if comment.author_id != user.id and not target.is_teacher:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only the author or a classroom teacher can delete this comment",
            )
        ensure_not_archived(target.is_archived)

        await self.db.delete(comment)
        await self.db.commit()