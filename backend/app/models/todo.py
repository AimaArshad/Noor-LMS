"""To-do items shown on the student/teacher To-Do page."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, UniqueConstraint, false
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models._helpers import CreatedAtMixin, pg_enum, uuid_fk
from app.models.enums import TodoRefType

if TYPE_CHECKING:
    from app.models.user import User


class TodoItem(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A per-user task, usually derived from an assignment or quiz.

    ``ref_type`` / ``ref_id`` are either both set (derived item) or both NULL
    (personal item). One derived item exists per (user, reference).
    """

    __tablename__ = "todo_items"
    __table_args__ = (
        UniqueConstraint("user_id", "ref_type", "ref_id", name="uq_todo_items_user_ref"),
        CheckConstraint("(ref_type IS NULL) = (ref_id IS NULL)", name="ref_pair"),
        Index("ix_todo_items_user_id_is_done_due_at", "user_id", "is_done", "due_at"),
    )

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE", index=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ref_type: Mapped[TodoRefType | None] = mapped_column(pg_enum(TodoRefType, "todo_ref_type"))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    user: Mapped[User] = relationship(back_populates="todo_items")

    def __repr__(self) -> str:
        return f"<TodoItem {self.title!r} done={self.is_done}>"