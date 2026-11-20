"""audiobook feature: audiobooks, audiobook_sections, audiobook_segments, playback_progress

Revision ID: d4b8f2c71a09
Revises: c9f3a1e8d047
Create Date: 2026-11-20 00:00:00

New tables
----------
* audiobooks               — one per document per classroom
* audiobook_sections       — extracted chapters/topics (trigram index on title_norm)
* audiobook_segments       — TTS units, unique(audiobook_id, seq)
* playback_progress        — per-user resume state

New ENUM types
--------------
* audiobook_status   (queued | extracting | synthesizing | ready | failed | needs_ocr)
* segment_status     (pending | ready | failed)

New extension
-------------
* pg_trgm (CREATE EXTENSION IF NOT EXISTS)
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4b8f2c71a09"
down_revision: Union[str, None] = "c9f3a1e8d047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Enum helpers
# ---------------------------------------------------------------------------

audiobook_status = postgresql.ENUM(
    "queued", "extracting", "synthesizing", "ready", "failed", "needs_ocr",
    name="audiobook_status",
    create_type=False,
)
segment_status = postgresql.ENUM(
    "pending", "ready", "failed",
    name="segment_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # Enable trigram extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Create ENUM types
    audiobook_status.create(bind, checkfirst=True)
    segment_status.create(bind, checkfirst=True)

    # ------------------------------------------------------------------ #
    # audiobooks
    # ------------------------------------------------------------------ #
    op.create_table(
        "audiobooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("classroom_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column(
            "status",
            audiobook_status,
            nullable=False,
            server_default="queued",
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column(
            "pages_approximate",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("total_duration_ms", sa.BigInteger, nullable=True),
        sa.Column("voice", sa.String(100), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"], ["classrooms.id"],
            name=op.f("fk_audiobooks_classroom_id_classrooms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["files.id"],
            name=op.f("fk_audiobooks_file_id_files"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name=op.f("fk_audiobooks_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audiobooks")),
    )
    op.create_index(op.f("ix_audiobooks_classroom_id"), "audiobooks", ["classroom_id"])
    op.create_index(op.f("ix_audiobooks_file_id"), "audiobooks", ["file_id"])
    op.create_index(op.f("ix_audiobooks_created_by"), "audiobooks", ["created_by"])

    # ------------------------------------------------------------------ #
    # audiobook_sections
    # ------------------------------------------------------------------ #
    op.create_table(
        "audiobook_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("audiobook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("level", sa.SmallInteger, nullable=False),
        sa.Column("number", sa.Integer, nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("title_norm", sa.String(512), nullable=False),
        sa.Column("start_page", sa.Integer, nullable=False),
        sa.Column("end_page", sa.Integer, nullable=True),
        sa.Column("first_segment_seq", sa.Integer, nullable=True),
        sa.Column("last_segment_seq", sa.Integer, nullable=True),
        sa.ForeignKeyConstraint(
            ["audiobook_id"], ["audiobooks.id"],
            name=op.f("fk_audiobook_sections_audiobook_id_audiobooks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["audiobook_sections.id"],
            name=op.f("fk_audiobook_sections_parent_id_audiobook_sections"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audiobook_sections")),
    )
    op.create_index(
        "ix_audiobook_sections_audiobook_id_seq",
        "audiobook_sections",
        ["audiobook_id", "seq"],
    )
    op.create_index(
        op.f("ix_audiobook_sections_parent_id"),
        "audiobook_sections",
        ["parent_id"],
    )
    # GIN trigram index for fuzzy section title search
    op.execute(
        "CREATE INDEX ix_audiobook_sections_title_norm_trgm "
        "ON audiobook_sections USING gin (title_norm gin_trgm_ops)"
    )

    # ------------------------------------------------------------------ #
    # audiobook_segments
    # ------------------------------------------------------------------ #
    op.create_table(
        "audiobook_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("audiobook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_index", sa.Integer, nullable=False),
        sa.Column("page_label", sa.String(32), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("char_count", sa.Integer, nullable=False),
        sa.Column("audio_key", sa.String(1024), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "status",
            segment_status,
            nullable=False,
            server_default="pending",
        ),
        sa.ForeignKeyConstraint(
            ["audiobook_id"], ["audiobooks.id"],
            name=op.f("fk_audiobook_segments_audiobook_id_audiobooks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["section_id"], ["audiobook_sections.id"],
            name=op.f("fk_audiobook_segments_section_id_audiobook_sections"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audiobook_segments")),
        sa.UniqueConstraint(
            "audiobook_id", "seq",
            name="uq_audiobook_segments_audiobook_id_seq",
        ),
    )
    op.create_index(
        "ix_audiobook_segments_audiobook_id_seq",
        "audiobook_segments",
        ["audiobook_id", "seq"],
    )
    op.create_index(
        "ix_audiobook_segments_section_id",
        "audiobook_segments",
        ["section_id"],
    )
    op.create_index(
        "ix_audiobook_segments_page_index",
        "audiobook_segments",
        ["page_index"],
    )
    # GIN full-text search index on segment text
    op.execute(
        "CREATE INDEX ix_audiobook_segments_text_fts "
        "ON audiobook_segments USING gin (to_tsvector('english', text))"
    )

    # ------------------------------------------------------------------ #
    # playback_progress
    # ------------------------------------------------------------------ #
    op.create_table(
        "playback_progress",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("audiobook_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("segment_seq", sa.Integer, nullable=False),
        sa.Column("offset_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_playback_progress_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["audiobook_id"], ["audiobooks.id"],
            name=op.f("fk_playback_progress_audiobook_id_audiobooks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "audiobook_id", name=op.f("pk_playback_progress")),
    )
    op.create_index(
        "ix_playback_progress_user_id",
        "playback_progress",
        ["user_id"],
    )
    op.create_index(
        "ix_playback_progress_audiobook_id",
        "playback_progress",
        ["audiobook_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("playback_progress")
    op.drop_table("audiobook_segments")
    op.drop_table("audiobook_sections")
    op.drop_table("audiobooks")

    audiobook_status.drop(bind, checkfirst=True)
    segment_status.drop(bind, checkfirst=True)

    # Note: we do NOT drop pg_trgm — other extensions may rely on it.

