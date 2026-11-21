"""Classroom and classroom membership models."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, false, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._helpers import pg_enum, uuid_fk
from app.models.enums import MemberRole

if TYPE_CHECKING:
    from app.models.announcement import Announcement
    from app.models.assignment import Assignment
    from app.models.audiobook import Audiobook
    from app.models.material import Material
    from app.models.quiz import Quiz
    from app.models.user import User

# No 0/O/1/I/L to avoid transcription mistakes when students type the code.
_JOIN_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_join_code(length: int = 7) -> str:
    """Return a cryptographically random, human-friendly join code.

    Uniqueness is guaranteed by the DB constraint; the service layer should retry
    on ``IntegrityError`` (collision probability is negligible).
    """
    return "".join(secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(length))


class Classroom(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A class (course) owned by a teacher, joined by students via ``join_code``."""

    __tablename__ = "classrooms"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    section: Mapped[str | None] = mapped_column(String(100))
    subject: Mapped[str | None] = mapped_column(String(100))
    room: Mapped[str | None] = mapped_column(String(100))
    # RESTRICT: a user who owns classrooms cannot be hard-deleted until the
    # classrooms are transferred or deleted.
    owner_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="RESTRICT")
    join_code: Mapped[str] = mapped_column(
        String(16), unique=True, index=True, nullable=False, default=generate_join_code
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    # --- Relationships -------------------------------------------------- #
    owner: Mapped[User] = relationship(back_populates="owned_classrooms")
    members: Mapped[list[ClassroomMember]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan", passive_deletes=True
    )
    # NOTE: announcements & assignments intentionally do NOT use passive_deletes.
    # Deleting them through the ORM fires the mapper events in comment.py that
    # remove their (polymorphic, FK-less) comments.
    announcements: Mapped[list[Announcement]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )
    quizzes: Mapped[list[Quiz]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan", passive_deletes=True
    )
    materials: Mapped[list[Material]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan", passive_deletes=True
    )
    audiobooks: Mapped[list[Audiobook]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Classroom {self.name!r} code={self.join_code}>"


class ClassroomMember(Base):
    """Association between a user and a classroom (composite primary key)."""

    __tablename__ = "classroom_members"

    classroom_id: Mapped[uuid.UUID] = uuid_fk(
        "classrooms.id", ondelete="CASCADE", primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,  # "which classrooms is this user in?"
    )
    role: Mapped[MemberRole] = mapped_column(
        pg_enum(MemberRole, "member_role"),
        nullable=False,
        default=MemberRole.STUDENT,
        server_default=MemberRole.STUDENT.value,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    classroom: Mapped[Classroom] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")

    def __repr__(self) -> str:
        return (
            f"<ClassroomMember classroom={self.classroom_id} "
            f"user={self.user_id} role={self.role}>"
        )