"""In-app notifications."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models._helpers import CreatedAtMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.user import User


class Notification(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A notification delivered to a single user.

    ``type`` is a free-form string (e.g. ``assignment_posted``, ``grade_returned``,
    ``comment_added``) so new kinds do not require a DB migration.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        # Covers: unread count, unread list, and newest-first listing per user.
        Index("ix_notifications_user_id_is_read_created_at", "user_id", "is_read", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE", index=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="general", server_default="general"
    )
    link: Mapped[str | None] = mapped_column(String(1024))
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    user: Mapped[User] = relationship(back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification {self.type} read={self.is_read}>"