"""Class materials (resources shared by the teacher)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._helpers import jsonb_list, uuid_fk

if TYPE_CHECKING:
    from app.models.classroom import Classroom


class Material(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A resource (notes, slides, links, files) posted to the classwork tab."""

    __tablename__ = "materials"
    __table_args__ = (
        Index("ix_materials_classroom_id_created_at", "classroom_id", "created_at"),
    )

    classroom_id: Mapped[uuid.UUID] = uuid_fk("classrooms.id", ondelete="CASCADE", index=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    attachments: Mapped[list[dict[str, Any]]] = jsonb_list()

    classroom: Mapped[Classroom] = relationship(back_populates="materials")

    def __repr__(self) -> str:
        return f"<Material {self.title!r}>"