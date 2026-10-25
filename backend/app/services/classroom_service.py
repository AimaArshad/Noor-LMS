"""Classroom business logic: create, list, update, delete, join, leave, people."""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.models import Classroom, ClassroomMember, MemberRole, User
from app.models.classroom import generate_join_code
from app.schemas.classrooms import (
    ClassroomCreate,
    ClassroomDetail,
    ClassroomMemberRead,
    ClassroomPeople,
    ClassroomRead,
    ClassroomUpdate,
)

logger = logging.getLogger("educonnect.classrooms")

_JOIN_CODE_ATTEMPTS = 5


class ClassroomService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Presentation helper
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_detail(classroom: Classroom, role: MemberRole) -> ClassroomDetail:
        """Build the API response; the join code is revealed to teachers only."""
        base = ClassroomRead.model_validate(classroom).model_dump()
        return ClassroomDetail(
            **base,
            my_role=role,
            join_code=classroom.join_code if role == MemberRole.TEACHER else None,
        )

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #
    async def create(self, owner: User, data: ClassroomCreate) -> Classroom:
        """Create a classroom and add the owner as a teacher member (one transaction).

        Raises:
            HTTPException: 503 if a unique join code could not be generated.
        """
        owner_id = owner.id  # read now: a rollback below expires ORM attributes
        for _ in range(_JOIN_CODE_ATTEMPTS):
            classroom = Classroom(
                name=data.name,
                section=data.section,
                subject=data.subject,
                room=data.room,
                owner_id=owner_id,
                join_code=generate_join_code(),
            )
            classroom.members.append(ClassroomMember(user_id=owner_id, role=MemberRole.TEACHER))
            self.db.add(classroom)
            try:
                await self.db.commit()
            except IntegrityError as exc:
                await self.db.rollback()
                if "join_code" not in str(exc.orig):
                    raise
                logger.warning("Join code collision, retrying")
                continue
            await self.db.refresh(classroom)  # load server-generated timestamps
            return classroom

        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Could not generate a join code, please retry"
        )

    # ------------------------------------------------------------------ #
    # List
    # ------------------------------------------------------------------ #
    async def list_for_user(
        self,
        user: User,
        *,
        include_archived: bool,
        limit: int,
        offset: int,
    ) -> list[tuple[Classroom, MemberRole]]:
        """Classrooms the user is a member of, newest first, with the user's role."""
        stmt = (
            select(Classroom, ClassroomMember.role)
            .join(ClassroomMember, ClassroomMember.classroom_id == Classroom.id)
            .where(ClassroomMember.user_id == user.id)
        )
        if not include_archived:
            stmt = stmt.where(Classroom.is_archived.is_(False))
        stmt = stmt.order_by(Classroom.created_at.desc(), Classroom.id).limit(limit).offset(offset)
        return [(classroom, role) for classroom, role in (await self.db.execute(stmt)).all()]

    # ------------------------------------------------------------------ #
    # Update / delete
    # ------------------------------------------------------------------ #
    async def update(self, classroom: Classroom, data: ClassroomUpdate) -> Classroom:
        """Apply a PATCH body (only the fields the client actually sent)."""
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(classroom, field, value)
        await self.db.commit()
        await self.db.refresh(classroom)  # pick up the DB-side updated_at
        return classroom

    async def delete(self, classroom: Classroom) -> None:
        """Delete a classroom and everything in it.

        Announcements/assignments are deleted through the ORM (so their comments are
        cleaned up by the mapper listeners); the rest cascades inside PostgreSQL.
        """
        await self.db.delete(classroom)
        await self.db.commit()

    # ------------------------------------------------------------------ #
    # Join / leave
    # ------------------------------------------------------------------ #
    async def join(self, user: User, code: str) -> Classroom:
        """Join a classroom as a student using its join code.

        Raises:
            HTTPException: 404 invalid code, 403 archived classroom, 409 already a member.
        """
        classroom = await self.db.scalar(select(Classroom).where(Classroom.join_code == code))
        if classroom is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Invalid join code")
        if classroom.is_archived:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "This classroom is archived and not accepting members"
            )

        already = HTTPException(status.HTTP_409_CONFLICT, "You are already a member of this classroom")
        if await self.db.get(ClassroomMember, (classroom.id, user.id)) is not None:
            raise already

        self.db.add(
            ClassroomMember(classroom_id=classroom.id, user_id=user.id, role=MemberRole.STUDENT)
        )
        try:
            await self.db.commit()
        except IntegrityError as exc:  # concurrent double-click / duplicate request
            await self.db.rollback()
            raise already from exc
        return classroom

    async def leave(
        self, classroom: Classroom, user: User, member: ClassroomMember | None
    ) -> None:
        """Remove the caller's membership.

        Raises:
            HTTPException: 404 if not a member, 409 if the caller owns the classroom.
        """
        if member is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "You are not a member of this classroom")
        if classroom.owner_id == user.id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "The owner cannot leave the classroom. Delete it instead.",
            )
        await self.db.delete(member)
        await self.db.commit()

    # ------------------------------------------------------------------ #
    # People
    # ------------------------------------------------------------------ #
    async def list_people(self, classroom: Classroom) -> ClassroomPeople:
        """Teachers (owner first) and students (alphabetical) of a classroom."""
        stmt = (
            select(ClassroomMember)
            .join(ClassroomMember.user)
            .options(contains_eager(ClassroomMember.user))
            .where(ClassroomMember.classroom_id == classroom.id, User.is_active.is_(True))
            .order_by(User.full_name, User.id)
        )
        members = (await self.db.scalars(stmt)).all()

        owner_id: uuid.UUID = classroom.owner_id
        teachers = sorted(
            (m for m in members if m.role == MemberRole.TEACHER),
            key=lambda m: (m.user_id != owner_id, m.user.full_name.casefold()),
        )
        students = [m for m in members if m.role == MemberRole.STUDENT]
        return ClassroomPeople(
            teachers=[ClassroomMemberRead.model_validate(m) for m in teachers],
            students=[ClassroomMemberRead.model_validate(m) for m in students],
        )