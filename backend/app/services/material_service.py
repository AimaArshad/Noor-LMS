"""Material business logic. Every method is scoped to one classroom."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Classroom, Material, User
from app.schemas.common import AttachmentRef, Page
from app.schemas.materials import MaterialCreate, MaterialRead, MaterialUpdate
from app.services import todo_sync
from app.services.file_service import FileService
from app.services.guards import ensure_not_archived
from app.services.notification_service import stage_notifications

from fastapi import HTTPException, status


class MaterialService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession, files: FileService) -> None:
        self.db = db
        self.files = files

    # ------------------------------------------------------------------ #
    async def _resolve_attachments(
        self, user: User, refs: list[AttachmentRef], current: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Canonical JSONB attachments for ``refs``.

        Files already attached are kept as they are (a co-teacher can edit a material whose
        files another teacher uploaded); only NEW file ids go through the ownership check.
        """
        kept = {item["file_id"]: item for item in current}
        fresh = [ref for ref in refs if str(ref.file_id) not in kept]
        resolved = {d["file_id"]: d for d in await self.files.resolve_attachments(user, fresh)}
        return [kept.get(str(ref.file_id)) or resolved[str(ref.file_id)] for ref in refs]

    # ------------------------------------------------------------------ #
    async def get(self, classroom_id: uuid.UUID, material_id: uuid.UUID) -> Material:
        """Return a material of ``classroom_id``.

        Raises:
            HTTPException: 404 when it does not exist in this classroom.
        """
        material = await self.db.scalar(
            select(Material).where(Material.id == material_id, Material.classroom_id == classroom_id)
        )
        if material is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
        return material

    async def list_for_classroom(
        self, classroom_id: uuid.UUID, *, limit: int, offset: int
    ) -> Page[MaterialRead]:
        """Newest-first page of the classroom's materials."""
        total = (
            await self.db.scalar(
                select(func.count()).select_from(Material).where(Material.classroom_id == classroom_id)
            )
            or 0
        )
        rows = (
            await self.db.scalars(
                select(Material)
                .where(Material.classroom_id == classroom_id)
                .order_by(Material.created_at.desc(), Material.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return Page[MaterialRead](
            items=[MaterialRead.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------ #
    async def create(self, classroom: Classroom, user: User, data: MaterialCreate) -> Material:
        """Post a material and notify the classroom's students.

        Raises:
            HTTPException: 403 archived classroom, 422 invalid attachment.
        """
        ensure_not_archived(classroom.is_archived)
        attachments = await self.files.resolve_attachments(user, data.attachments)
        material = Material(
            classroom_id=classroom.id,
            title=data.title,
            description=data.description,
            attachments=attachments,
        )
        self.db.add(material)
        await self.db.flush()  # assigns material.id

        stage_notifications(
            self.db,
            await todo_sync.active_student_ids(self.db, classroom.id),
            title=f"New material: {material.title}",
            type="material_posted",
            link=f"/classrooms/{classroom.id}/materials/{material.id}",
        )
        await self.db.commit()
        await self.db.refresh(material)  # server-generated timestamps

        # Auto-create audiobooks for PDF/DOCX/TXT attachments (never fails the request)
        await self._auto_create_audiobooks(classroom, user, attachments)
        await self.db.refresh(material)  # a rolled-back audiobook insert expires loaded rows

        return material

    async def update(
        self, classroom: Classroom, user: User, material: Material, data: MaterialUpdate
    ) -> Material:
        """Apply a PATCH body (only the fields the client sent).

        Raises:
            HTTPException: 403 archived classroom, 422 invalid attachment.
        """
        ensure_not_archived(classroom.is_archived)
        changes = data.model_dump(exclude_unset=True)
        changes.pop("attachments", None)  # handled separately (UUID -> JSON-safe dicts)

        if data.attachments is not None:
            material.attachments = await self._resolve_attachments(
                user, data.attachments, material.attachments
            )

        for field, value in changes.items():
            setattr(material, field, value)
        await self.db.commit()
        await self.db.refresh(material)

        # Only after the material is safely saved: auto-create audiobooks for its files
        if data.attachments is not None:
            await self._auto_create_audiobooks(classroom, user, material.attachments)
            await self.db.refresh(material)
        return material

    async def delete(self, classroom: Classroom, material: Material) -> None:
        """Delete a material. Its files stay uploaded (and become deletable by their uploader)."""
        ensure_not_archived(classroom.is_archived)
        await self.db.delete(material)
        await self.db.commit()

    # ------------------------------------------------------------------ #
    # Audiobook auto-creation (idempotent, never raises)
    # ------------------------------------------------------------------ #

    async def _auto_create_audiobooks(
        self,
        classroom: Classroom,
        user: User,
        attachments: list[dict[str, Any]],
    ) -> None:
        """For each attachment, idempotently create an audiobook row + enqueue the build."""
        from app.services.audiobook_service import AudiobookService

        try:
            svc = AudiobookService(self.db)
            for att in attachments:
                try:
                    file_id = uuid.UUID(str(att["file_id"]))
                    await svc.auto_create_from_material(
                        classroom, file_id, "", created_by=user.id,
                        file_name=att.get("name", ""),
                    )
                except Exception:  # noqa: BLE001
                    await self.db.rollback()  # a failed insert must not poison the session
        except Exception:  # noqa: BLE001
            await self.db.rollback()



