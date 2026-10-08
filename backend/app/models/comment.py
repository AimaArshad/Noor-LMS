"""Polymorphic comments on assignments and announcements."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Index, Text, delete, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models._helpers import CreatedAtMixin, pg_enum, uuid_fk
from app.models.announcement import Announcement
from app.models.assignment import Assignment
from app.models.enums import CommentTarget
from app.models.user import User


class Comment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A comment attached to an assignment or announcement.

    ``target_id`` is intentionally **not** a foreign key (it points at different
    tables depending on ``target_type``). Referential cleanup is handled by the
    ``after_delete`` mapper listeners below.
    """

    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_target_type_target_id", "target_type", "target_id"),
    )

    author_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", ondelete="SET NULL", nullable=True)
    target_type: Mapped[CommentTarget] = mapped_column(
        pg_enum(CommentTarget, "comment_target_type"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    author: Mapped[User | None] = relationship()

    def __repr__(self) -> str:
        return f"<Comment {self.id} on {self.target_type}:{self.target_id}>"


def _cascade_delete_comments(target_type: CommentTarget):  # type: ignore[no-untyped-def]
    """Build a mapper listener that deletes comments of a deleted target row."""

    def _listener(_mapper: Mapper[Any], connection: Connection, target: Any) -> None:
        table = Comment.__table__
        connection.execute(
            delete(table).where(
                table.c.target_type == target_type,
                table.c.target_id == target.id,
            )
        )

    return _listener


# Fired when an Assignment/Announcement is deleted through the ORM
# (session.delete(obj), including cascades from Classroom).
# Bulk deletes (``delete(Assignment).where(...)``) or raw SQL bypass these hooks;
# if you use them, delete the related comments explicitly.
event.listen(Assignment, "after_delete", _cascade_delete_comments(CommentTarget.ASSIGNMENT))
event.listen(Announcement, "after_delete", _cascade_delete_comments(CommentTarget.ANNOUNCEMENT))