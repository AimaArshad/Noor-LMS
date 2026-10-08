"""Enumerations shared by ORM models and (later) Pydantic schemas.

Values are stored in PostgreSQL as native ENUM types using the lowercase
``value`` (not the member name). See :func:`app.models._helpers.pg_enum`.
"""

from __future__ import annotations

import enum


class UserRole(enum.StrEnum):
    """Global platform role of a user."""

    TEACHER = "teacher"
    STUDENT = "student"
    ADMIN = "admin"


class MemberRole(enum.StrEnum):
    """Role of a user *inside* a specific classroom."""

    TEACHER = "teacher"
    STUDENT = "student"


class AssignmentState(enum.StrEnum):
    """Publication state of an assignment."""

    DRAFT = "draft"
    PUBLISHED = "published"


class SubmissionState(enum.StrEnum):
    """Lifecycle of a student's submission."""

    ASSIGNED = "assigned"
    TURNED_IN = "turned_in"
    GRADED = "graded"
    RETURNED = "returned"


class QuestionType(enum.StrEnum):
    """Supported quiz question types."""

    MCQ = "mcq"
    SHORT_ANSWER = "short_answer"
    TRUE_FALSE = "true_false"


class CommentTarget(enum.StrEnum):
    """Entity a comment is attached to (polymorphic target)."""

    ASSIGNMENT = "assignment"
    ANNOUNCEMENT = "announcement"


class TodoRefType(enum.StrEnum):
    """Entity a to-do item was derived from."""

    ASSIGNMENT = "assignment"
    QUIZ = "quiz"