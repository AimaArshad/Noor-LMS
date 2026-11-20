# """Audiobook ORM models.

# Tables
# ------
# audiobooks              — one per uploaded document per classroom
# audiobook_sections      — extracted chapters/topics with trigram index on title_norm
# audiobook_segments      — smallest TTS unit; unique(audiobook_id, seq)
# playback_progress       — per-user resume position (PK: user_id, audiobook_id)
# """

# from __future__ import annotations

# import uuid
# from typing import TYPE_CHECKING

# from sqlalchemy import (
#     BigInteger,
#     Boolean,
#     ForeignKey,
#     Index,
#     Integer,
#     SmallInteger,
#     String,
#     Text,
#     UniqueConstraint,
#     false,
#     text,
# )
# from sqlalchemy.dialects.postgresql import UUID
# from sqlalchemy.orm import Mapped, mapped_column, relationship

# from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
# from app.models._helpers import CreatedAtMixin, pg_enum, uuid_fk
# from app.models.audiobook_enums import AudiobookStatus, SegmentStatus

# if TYPE_CHECKING:
#     from app.models.classroom import Classroom
#     from app.models.file import File
#     from app.models.user import User

# from sqlalchemy import Index, text
# from sqlalchemy.dialects.postgresql import TSVECTOR
# # ---------------------------------------------------------------------------
# # audiobooks
# # ---------------------------------------------------------------------------

# class Audiobook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
#     """One audiobook entry per classroom + source file combination."""

#     __tablename__ = "audiobooks"

#     classroom_id: Mapped[uuid.UUID] = uuid_fk("classrooms.id", ondelete="CASCADE")
#     file_id: Mapped[uuid.UUID] = uuid_fk("files.id", ondelete="CASCADE")

#     title: Mapped[str] = mapped_column(String(512), nullable=False)
#     status: Mapped[AudiobookStatus] = mapped_column(
#         pg_enum(AudiobookStatus, "audiobook_status"),
#         nullable=False,
#         default=AudiobookStatus.QUEUED,
#         server_default=AudiobookStatus.QUEUED.value,
#     )
#     error: Mapped[str | None] = mapped_column(Text, nullable=True)
#     page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
#     pages_approximate: Mapped[bool] = mapped_column(
#         Boolean, nullable=False, default=False, server_default=false()
#     )
#     total_duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
#     voice: Mapped[str | None] = mapped_column(String(100), nullable=True)

#     # SET NULL: audiobook record survives teacher account deletion
#     created_by: Mapped[uuid.UUID | None] = uuid_fk(
#         "users.id", ondelete="SET NULL", nullable=True
#     )

#     # --- Relationships --- #
#     sections: Mapped[list[AudiobookSection]] = relationship(
#         back_populates="audiobook",
#         cascade="all, delete-orphan",
#         passive_deletes=True,
#         order_by="AudiobookSection.seq",
#     )
#     segments: Mapped[list[AudiobookSegment]] = relationship(
#         back_populates="audiobook",
#         cascade="all, delete-orphan",
#         passive_deletes=True,
#         order_by="AudiobookSegment.seq",
#     )

#     def __repr__(self) -> str:
#         return f"<Audiobook {self.title!r} status={self.status}>"


# # ---------------------------------------------------------------------------
# # audiobook_sections
# # ---------------------------------------------------------------------------

# class AudiobookSection(UUIDPrimaryKeyMixin, Base):
#     """One chapter or topic within an audiobook."""

#     __tablename__ = "audiobook_sections"
#     __table_args__ = (
#         # Trigram index for fast fuzzy search on the normalised title.
#         # Using GIN with pg_trgm: op_class set via DDL in the migration.
#         # (Defined in the migration; here we just declare the ORM-level index
#         #  so autogenerate knows about it.)
      
#        # This tells Alembic it is an FTS index and not a standard index
#         Index(
#             "ix_audiobook_segments_text_fts",
#             text("to_tsvector('english', text)"),
#             postgresql_using="gin",
#         ),

#         Index(
#             "ix_audiobook_sections_title_norm_trgm",
#             "title_norm",
#             postgresql_using="gin",
#             postgresql_ops={"title_norm": "gin_trgm_ops"},
#         ),
#         Index(
#             "ix_audiobook_sections_audiobook_id_seq",
#             "audiobook_id",
#             "seq",
#         ),
#     )

#     audiobook_id: Mapped[uuid.UUID] = uuid_fk(
#         "audiobooks.id", ondelete="CASCADE", index=False  # covered by composite idx
#     )
#     seq: Mapped[int] = mapped_column(Integer, nullable=False)

#     # Self-referential parent (nullable for top-level chapters)
#     parent_id: Mapped[uuid.UUID | None] = mapped_column(
#         UUID(as_uuid=True),
#         ForeignKey("audiobook_sections.id", ondelete="SET NULL"),
#         nullable=True,
#         index=True,
#     )

#     level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
#     number: Mapped[int | None] = mapped_column(Integer, nullable=True)
#     title: Mapped[str] = mapped_column(String(512), nullable=False)
#     title_norm: Mapped[str] = mapped_column(String(512), nullable=False)
#     start_page: Mapped[int] = mapped_column(Integer, nullable=False)
#     end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
#     first_segment_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
#     last_segment_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)

#     audiobook: Mapped[Audiobook] = relationship(back_populates="sections")

#     def __repr__(self) -> str:
#         return f"<AudiobookSection level={self.level} title={self.title!r}>"


# # ---------------------------------------------------------------------------
# # audiobook_segments
# # ---------------------------------------------------------------------------

# class AudiobookSegment(UUIDPrimaryKeyMixin, Base):
#     """One TTS synthesis unit (800-1500 chars) in playback order."""

#     __tablename__ = "audiobook_segments"
#     __table_args__ = (
#         UniqueConstraint(
#             "audiobook_id", "seq",
#             name="uq_audiobook_segments_audiobook_id_seq",
#         ),
#         # GIN full-text index for search within a book
#         Index(
#             "ix_audiobook_segments_text_fts",
#             "text",
#             postgresql_using="gin",
#             postgresql_ops={"text": "to_tsvector('english', text)"},
#         ),
#         Index("ix_audiobook_segments_audiobook_id_seq", "audiobook_id", "seq"),
#         Index("ix_audiobook_segments_section_id", "section_id"),
#     )

#     audiobook_id: Mapped[uuid.UUID] = uuid_fk(
#         "audiobooks.id", ondelete="CASCADE", index=False  # covered by composite idx
#     )
#     seq: Mapped[int] = mapped_column(Integer, nullable=False)
#     section_id: Mapped[uuid.UUID | None] = mapped_column(
#         UUID(as_uuid=True),
#         ForeignKey("audiobook_sections.id", ondelete="SET NULL"),
#         nullable=True,
#         index=False,  # covered by explicit idx above
#     )
#     page_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
#     page_label: Mapped[str] = mapped_column(String(32), nullable=False)
#     text: Mapped[str] = mapped_column(Text, nullable=False)
#     char_count: Mapped[int] = mapped_column(Integer, nullable=False)
#     audio_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
#     duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
#     status: Mapped[SegmentStatus] = mapped_column(
#         pg_enum(SegmentStatus, "segment_status"),
#         nullable=False,
#         default=SegmentStatus.PENDING,
#         server_default=SegmentStatus.PENDING.value,
#     )

#     audiobook: Mapped[Audiobook] = relationship(back_populates="segments")

#     def __repr__(self) -> str:
#         return f"<AudiobookSegment seq={self.seq} chars={self.char_count}>"


# # ---------------------------------------------------------------------------
# # playback_progress
# # ---------------------------------------------------------------------------

# class PlaybackProgress(Base):
#     """Per-user resume position inside an audiobook (composite PK)."""

#     __tablename__ = "playback_progress"
#     __table_args__ = (
#         Index("ix_playback_progress_user_id", "user_id"),
#         Index("ix_playback_progress_audiobook_id", "audiobook_id"),
#     )

#     user_id: Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True),
#         ForeignKey("users.id", ondelete="CASCADE"),
#         primary_key=True,
#         nullable=False,
#     )
#     audiobook_id: Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True),
#         ForeignKey("audiobooks.id", ondelete="CASCADE"),
#         primary_key=True,
#         nullable=False,
#     )
#     segment_seq: Mapped[int] = mapped_column(Integer, nullable=False)
#     offset_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

#     # updated_at without full TimestampMixin (no created_at)
#     from sqlalchemy import DateTime, func

#     updated_at: Mapped[object] = mapped_column(
#         DateTime(timezone=True),
#         server_default=func.now(),
#         onupdate=func.now(),
#         nullable=False,
#     )

#     def __repr__(self) -> str:
#         return f"<PlaybackProgress user={self.user_id} audiobook={self.audiobook_id} seq={self.segment_seq}>"



"""Audiobook ORM models.

Tables
------
audiobooks              — one per uploaded document per classroom
audiobook_sections      — extracted chapters/topics with trigram index on title_norm
audiobook_segments      — smallest TTS unit; unique(audiobook_id, seq)
playback_progress       — per-user resume position (PK: user_id, audiobook_id)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._helpers import pg_enum, uuid_fk
from app.models.audiobook_enums import AudiobookStatus, SegmentStatus

if TYPE_CHECKING:
    from app.models.classroom import Classroom
    from app.models.file import File
    from app.models.user import User

# ---------------------------------------------------------------------------
# audiobooks
# ---------------------------------------------------------------------------

class Audiobook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One audiobook entry per classroom + source file combination."""

    __tablename__ = "audiobooks"

    classroom_id: Mapped[uuid.UUID] = uuid_fk("classrooms.id", ondelete="CASCADE")
    file_id: Mapped[uuid.UUID] = uuid_fk("files.id", ondelete="CASCADE")

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[AudiobookStatus] = mapped_column(
        pg_enum(AudiobookStatus, "audiobook_status"),
        nullable=False,
        default=AudiobookStatus.QUEUED,
        server_default=AudiobookStatus.QUEUED.value,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages_approximate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    total_duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    voice: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # SET NULL: audiobook record survives teacher account deletion
    created_by: Mapped[uuid.UUID | None] = uuid_fk(
        "users.id", ondelete="SET NULL", nullable=True
    )

    # --- Relationships --- #
    sections: Mapped[list[AudiobookSection]] = relationship(
        back_populates="audiobook",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AudiobookSection.seq",
    )
    segments: Mapped[list[AudiobookSegment]] = relationship(
        back_populates="audiobook",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AudiobookSegment.seq",
    )

    def __repr__(self) -> str:
        return f"<Audiobook {self.title!r} status={self.status}>"


# ---------------------------------------------------------------------------
# audiobook_sections
# ---------------------------------------------------------------------------

class AudiobookSection(UUIDPrimaryKeyMixin, Base):
    """One chapter or topic within an audiobook."""

    __tablename__ = "audiobook_sections"
    __table_args__ = (
        Index(
            "ix_audiobook_sections_title_norm_trgm",
            "title_norm",
            postgresql_using="gin",
            postgresql_ops={"title_norm": "gin_trgm_ops"},
        ),
        Index(
            "ix_audiobook_sections_audiobook_id_seq",
            "audiobook_id",
            "seq",
        ),
    )

    audiobook_id: Mapped[uuid.UUID] = uuid_fk(
        "audiobooks.id", ondelete="CASCADE", index=False  # covered by composite idx
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    # Self-referential parent (nullable for top-level chapters)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audiobook_sections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    title_norm: Mapped[str] = mapped_column(String(512), nullable=False)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_segment_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_segment_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)

    audiobook: Mapped[Audiobook] = relationship(back_populates="sections")

    def __repr__(self) -> str:
        return f"<AudiobookSection level={self.level} title={self.title!r}>"


# ---------------------------------------------------------------------------
# audiobook_segments
# ---------------------------------------------------------------------------

class AudiobookSegment(UUIDPrimaryKeyMixin, Base):
    """One TTS synthesis unit (800-1500 chars) in playback order."""

    __tablename__ = "audiobook_segments"
    __table_args__ = (
        UniqueConstraint(
            "audiobook_id", "seq",
            name="uq_audiobook_segments_audiobook_id_seq",
        ),
        # GIN full-text index for search within a book
        Index(
            "ix_audiobook_segments_text_fts",
            text("to_tsvector('english', text)"),
            postgresql_using="gin",
        ),
        Index("ix_audiobook_segments_audiobook_id_seq", "audiobook_id", "seq"),
        Index("ix_audiobook_segments_section_id", "section_id"),
    )

    audiobook_id: Mapped[uuid.UUID] = uuid_fk(
        "audiobooks.id", ondelete="CASCADE", index=False  # covered by composite idx
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audiobook_sections.id", ondelete="SET NULL"),
        nullable=True,
        index=False,  # covered by explicit idx above
    )
    page_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    page_label: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    audio_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[SegmentStatus] = mapped_column(
        pg_enum(SegmentStatus, "segment_status"),
        nullable=False,
        default=SegmentStatus.PENDING,
        server_default=SegmentStatus.PENDING.value,
    )

    audiobook: Mapped[Audiobook] = relationship(back_populates="segments")

    def __repr__(self) -> str:
        return f"<AudiobookSegment seq={self.seq} chars={self.char_count}>"


# ---------------------------------------------------------------------------
# playback_progress
# ---------------------------------------------------------------------------

class PlaybackProgress(Base):
    """Per-user resume position inside an audiobook (composite PK)."""

    __tablename__ = "playback_progress"
    __table_args__ = (
        Index("ix_playback_progress_user_id", "user_id"),
        Index("ix_playback_progress_audiobook_id", "audiobook_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    audiobook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audiobooks.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    segment_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    offset_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # updated_at without full TimestampMixin (no created_at)
    from sqlalchemy import DateTime, func

    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PlaybackProgress user={self.user_id} audiobook={self.audiobook_id} seq={self.segment_seq}>"