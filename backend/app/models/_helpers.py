"""Small helpers that keep model definitions concise and consistent."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column


def uuid_fk(
    target: str,
    *,
    ondelete: str,
    nullable: bool = False,
    index: bool = True,
    primary_key: bool = False,
) -> MappedColumn[Any]:
    """Create a UUID foreign-key column.

    Args:
        target: ``"table.column"`` the key points to.
        ondelete: Database-level ``ON DELETE`` action (CASCADE, SET NULL, RESTRICT).
        nullable: Whether the column accepts NULL.
        index: Create a b-tree index. Pass ``False`` when the column is already the
            leading column of a composite index / unique constraint / primary key.
        primary_key: Mark the column as (part of) the primary key.
    """
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        index=index and not primary_key,
        primary_key=primary_key,
    )


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Build a native PostgreSQL ENUM that persists member *values*."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda e: [member.value for member in e],
        validate_strings=True,
    )


def jsonb_list() -> MappedColumn[Any]:
    """JSONB column defaulting to an empty list (used for ``attachments``).

    Expected element shape::

        {"file_id": "<uuid>", "name": "report.pdf", "mime_type": "application/pdf"}
    """
    return mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )


class CreatedAtMixin:
    """Adds an immutable, timezone-aware ``created_at`` column."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )