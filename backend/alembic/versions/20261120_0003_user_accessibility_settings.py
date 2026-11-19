"""user_accessibility_settings: per-user accessibility preferences

Revision ID: c9f3a1e8d047
Revises: b7e2d4a91c35
Create Date: 2026-11-20 00:00:00

New table ``user_accessibility_settings``:
  * user_id UUID PK + FK → users.id ON DELETE CASCADE
  * tts_enabled, stt_enabled, high_contrast, large_text  BOOL NOT NULL DEFAULT false
  * tts_voice  VARCHAR(100) NULL
  * tts_speed  NUMERIC(4,2) NOT NULL DEFAULT 1.00
                CHECK (tts_speed BETWEEN 0.50 AND 2.00)
  * created_at / updated_at  TIMESTAMPTZ
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c9f3a1e8d047"
down_revision: Union[str, None] = "b7e2d4a91c35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_accessibility_settings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_user_accessibility_settings_user_id_users"),
            primary_key=True,
            nullable=False,
        ),
        # Accessibility flags
        sa.Column(
            "tts_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "stt_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "high_contrast",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "large_text",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # TTS preferences
        sa.Column("tts_voice", sa.String(100), nullable=True),
        sa.Column(
            "tts_speed",
            sa.Numeric(4, 2),
            nullable=False,
            server_default="1.00",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # DB-level speed range enforcement
        sa.CheckConstraint(
            "tts_speed BETWEEN 0.50 AND 2.00",
            name="ck_user_accessibility_settings_tts_speed_range",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_accessibility_settings")

