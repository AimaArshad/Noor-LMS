"""Uploaded file metadata (bytes live in the storage backend, not the DB)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models._helpers import CreatedAtMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.user import User


class File(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Metadata for an uploaded file.

    ``path`` is the key understood by the storage backend (relative path for the
    local filesystem, object key for S3/MinIO). ``storage_backend`` allows mixed
    backends during a migration from local disk to S3.
    """

    __tablename__ = "files"
    __table_args__ = (CheckConstraint("size_bytes >= 0", name="size_non_negative"),)

    # SET NULL: files referenced by attachments survive an uploader's removal.
    uploader_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", ondelete="SET NULL", nullable=True)
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_backend: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", server_default="local"
    )

    uploader: Mapped[User | None] = relationship()

    def __repr__(self) -> str:
        return f"<File {self.original_name!r} {self.size_bytes}B>"