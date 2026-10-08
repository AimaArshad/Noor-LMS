"""User account model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._helpers import pg_enum
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.classroom import Classroom, ClassroomMember
    from app.models.assignment import Submission
    from app.models.notification import Notification
    from app.models.quiz import QuizAttempt
    from app.models.todo import TodoItem


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A person using the platform (teacher, student or admin).

    ``email`` must be stored lower-cased by the service layer.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"),
        nullable=False,
        default=UserRole.STUDENT,
        server_default=UserRole.STUDENT.value,
    )
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

    # --- Relationships -------------------------------------------------- #
    # passive_deletes=True: the database enforces ON DELETE rules; the ORM does
    # not load children just to delete/null them.
    owned_classrooms: Mapped[list[Classroom]] = relationship(
        back_populates="owner", passive_deletes=True
    )
    memberships: Mapped[list[ClassroomMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="student",
        foreign_keys="Submission.student_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    quiz_attempts: Mapped[list[QuizAttempt]] = relationship(
        back_populates="student", cascade="all, delete-orphan", passive_deletes=True
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    todo_items: Mapped[list[TodoItem]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"