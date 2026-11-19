"""User accessibility preferences.

This table is 1-to-1 with ``users`` (``user_id`` is both the PK and the FK).
A row is created lazily on the first PATCH; before that, the service returns
defaults so the front-end never has to handle a missing object.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, false
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserAccessibilitySettings(TimestampMixin, Base):
    """Per-user accessibility preferences.

    Stored separately from ``users`` to keep the main table small.
    Speed is stored as NUMERIC(4, 2) with a database-level CHECK so the
    constraint is enforced even if the Python layer is bypassed.
    """

    __tablename__ = "user_accessibility_settings"
    __table_args__ = (
        CheckConstraint(
            "tts_speed BETWEEN 0.50 AND 2.00",
            name="ck_user_accessibility_settings_tts_speed_range",
        ),
    )

    # user_id is both the primary key and a FK to users.id (ON DELETE CASCADE)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    # --- Accessibility flags ---
    tts_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    stt_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    high_contrast: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    large_text: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    # --- TTS preferences ---
    tts_voice: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tts_speed: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        default=Decimal("1.00"),
        server_default="1.00",
    )

    # --- Relationship ---
    user: Mapped[User] = relationship(back_populates="accessibility_settings")

    def __repr__(self) -> str:
        return f"<UserAccessibilitySettings user_id={self.user_id}>"
