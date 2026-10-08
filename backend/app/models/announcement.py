"""Classroom stream announcements."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._helpers import uuid_fk

if TYPE_CHECKING:
    from app.models.classroom import Classroom
    from app.models.user import User


class Announcement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A post made by a teacher to a classroom stream."""

    __tablename__ = "announcements"
    __table_args__ = (
        # Stream query: newest announcements of a classroom.
        Index("ix_announcements_classroom_id_created_at", "classroom_id", "created_at"),
    )

    classroom_id: Mapped[uuid.UUID] = uuid_fk(
        "classrooms.id", ondelete="CASCADE", index=False
    )
    # SET NULL keeps the post if the author account is removed.
    author_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", ondelete="SET NULL", nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    classroom: Mapped[Classroom] = relationship(back_populates="announcements")
    author: Mapped[User | None] = relationship()

    def __repr__(self) -> str:
        return f"<Announcement {self.id} classroom={self.classroom_id}>"