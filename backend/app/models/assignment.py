"""Assignments and student submissions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._helpers import jsonb_list, pg_enum, uuid_fk
from app.models.enums import AssignmentState, SubmissionState

if TYPE_CHECKING:
    from app.models.classroom import Classroom
    from app.models.user import User


class Assignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Work posted by a teacher. Students see it only when ``state == published``."""

    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("max_points >= 0", name="max_points_non_negative"),
        Index("ix_assignments_classroom_id_state", "classroom_id", "state"),
    )

    classroom_id: Mapped[uuid.UUID] = uuid_fk(
        "classrooms.id", ondelete="CASCADE", index=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    max_points: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )
    attachments: Mapped[list[dict[str, Any]]] = jsonb_list()
    state: Mapped[AssignmentState] = mapped_column(
        pg_enum(AssignmentState, "assignment_state"),
        nullable=False,
        default=AssignmentState.DRAFT,
        server_default=AssignmentState.DRAFT.value,
    )

    classroom: Mapped[Classroom] = relationship(back_populates="assignments")
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Assignment {self.title!r} state={self.state}>"


class Submission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A student's work for one assignment (at most one row per student)."""

    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_submissions_assignment_student"),
        CheckConstraint("grade IS NULL OR grade >= 0", name="grade_non_negative"),
    )

    # Leading column of the unique constraint above -> no extra index needed.
    assignment_id: Mapped[uuid.UUID] = uuid_fk(
        "assignments.id", ondelete="CASCADE", index=False
    )
    student_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE")
    content: Mapped[str | None] = mapped_column(Text)
    attachments: Mapped[list[dict[str, Any]]] = jsonb_list()
    state: Mapped[SubmissionState] = mapped_column(
        pg_enum(SubmissionState, "submission_state"),
        nullable=False,
        default=SubmissionState.ASSIGNED,
        server_default=SubmissionState.ASSIGNED.value,
    )
    grade: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    feedback: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graded_by: Mapped[uuid.UUID | None] = uuid_fk("users.id", ondelete="SET NULL", nullable=True)

    assignment: Mapped[Assignment] = relationship(back_populates="submissions")
    student: Mapped[User] = relationship(
        back_populates="submissions", foreign_keys=[student_id]
    )
    grader: Mapped[User | None] = relationship(foreign_keys=[graded_by])

    def __repr__(self) -> str:
        return f"<Submission {self.id} state={self.state}>"