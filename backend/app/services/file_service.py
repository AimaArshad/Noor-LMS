"""File business logic: validated uploads, access control, attachments, deletion."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

from fastapi import HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    Assignment,
    AssignmentState,
    ClassroomMember,
    File,
    Material,
    MemberRole,
    Submission,
    User,
    UserRole,
)
from app.schemas.common import AttachmentRef
from app.schemas.files import FileCreate
from app.services.storage import StorageBackend, StorageError, get_storage
from app.utils.file_types import (
    ALLOWED_EXTENSIONS,
    TYPE_BY_EXTENSION,
    get_extension,
    sanitize_filename,
)

logger = logging.getLogger("educonnect.files")


def _needle(file_id: uuid.UUID) -> list[dict[str, str]]:
    """JSONB containment probe: ``attachments @> [{"file_id": "<uuid>"}]``."""
    return [{"file_id": str(file_id)}]


class FileService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession, storage: StorageBackend) -> None:
        self.db = db
        self.storage = storage  # backend used for NEW uploads

    # ------------------------------------------------------------------ #
    # Backend selection
    # ------------------------------------------------------------------ #
    def backend_for(self, file: File) -> StorageBackend:
        """The backend that holds ``file`` (supports mixed local/S3 data)."""
        if file.storage_backend == self.storage.name:
            return self.storage
        try:
            return get_storage(file.storage_backend)
        except StorageError as exc:
            logger.error("Storage backend %r unavailable for file %s", file.storage_backend, file.id)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "File storage is unavailable"
            ) from exc

    # ------------------------------------------------------------------ #
    # Upload
    # ------------------------------------------------------------------ #
    async def upload(self, user: User, upload: UploadFile) -> File:
        """Validate and store an uploaded file, then persist its metadata.

        Raises:
            HTTPException: 400 empty file / bad name, 413 too large,
                415 type not allowed or content does not match the extension,
                503 storage failure.
        """
        uploader_id = user.id
        original_name = sanitize_filename(upload.filename)
        if not original_name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A file name is required")

        extension = get_extension(original_name)
        file_type = TYPE_BY_EXTENSION.get(extension)
        if file_type is None:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                f"File type '{extension or 'unknown'}' is not allowed. "
                f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        source = upload.file
        source.seek(0, os.SEEK_END)
        size = source.tell()
        source.seek(0)
        if size == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty")
        if size > settings.max_upload_size_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"File too large (maximum {settings.MAX_UPLOAD_SIZE_MB} MB)",
            )
        if not await asyncio.to_thread(file_type.matches, source):
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "File content does not match its extension"
            )

        stored_name = f"{uuid.uuid4().hex}{extension}"
        key = f"{stored_name[:2]}/{stored_name}"  # 256 shard directories
        try:
            dto = FileCreate(
                uploader_id=uploader_id,
                original_name=original_name,
                stored_name=stored_name,
                mime_type=file_type.mime,  # from the allow-list, never from the client
                size_bytes=size,
                path=key,
                storage_backend=self.storage.name,  # type: ignore[arg-type]
            )
        except ValidationError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid file name") from exc

        try:
            await self.storage.save(key, source, content_type=file_type.mime)
        except StorageError as exc:
            logger.exception("Storage write failed for %s", key)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "File storage is unavailable"
            ) from exc

        file = File(**dto.model_dump())
        self.db.add(file)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            await self._discard(self.storage, key)  # do not leave an orphan behind
            raise
        await self.db.refresh(file)  # load server-generated created_at
        return file

    # ------------------------------------------------------------------ #
    # Access control
    # ------------------------------------------------------------------ #
    async def can_access(self, file: File, user: User) -> bool:
        """Whether ``user`` may read ``file`` (see module docs for the rules)."""
        if user.role == UserRole.ADMIN or file.uploader_id == user.id:
            return True
        needle = _needle(file.id)

        # 1) Assignment attachments: members see them; students only when published.
        rows = (
            await self.db.execute(
                select(ClassroomMember.role, Assignment.state)
                .select_from(ClassroomMember)
                .join(Assignment, Assignment.classroom_id == ClassroomMember.classroom_id)
                .where(ClassroomMember.user_id == user.id, Assignment.attachments.contains(needle))
            )
        ).all()
        if any(
            role == MemberRole.TEACHER or state == AssignmentState.PUBLISHED for role, state in rows
        ):
            return True

        # 2) Material attachments: any member of the classroom.
        hit = await self.db.scalar(
            select(ClassroomMember.user_id)
            .select_from(ClassroomMember)
            .join(Material, Material.classroom_id == ClassroomMember.classroom_id)
            .where(ClassroomMember.user_id == user.id, Material.attachments.contains(needle))
            .limit(1)
        )
        if hit is not None:
            return True

        # 3) Submission attachments: the submitting student, or a teacher of that classroom.
        rows2 = (
            await self.db.execute(
                select(Submission.student_id, ClassroomMember.role)
                .select_from(Submission)
                .join(Assignment, Assignment.id == Submission.assignment_id)
                .join(
                    ClassroomMember,
                    and_(
                        ClassroomMember.classroom_id == Assignment.classroom_id,
                        ClassroomMember.user_id == user.id,
                    ),
                    isouter=True,
                )
                .where(Submission.attachments.contains(needle))
            )
        ).all()
        return any(
            student_id == user.id or role == MemberRole.TEACHER for student_id, role in rows2
        )

    async def get_accessible(self, user: User, file_id: uuid.UUID) -> File:
        """Return the file, or 404 when it is missing OR the caller may not see it."""
        file = await self.db.get(File, file_id)
        if file is None or not await self.can_access(file, user):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
        return file

    # ------------------------------------------------------------------ #
    # Attachments (used by assignments / submissions / materials in later steps)
    # ------------------------------------------------------------------ #
    async def resolve_attachments(
        self, user: User, refs: list[AttachmentRef]
    ) -> list[dict[str, Any]]:
        """Validate client-supplied attachment refs and return canonical JSONB dicts.

        Every file must exist and have been uploaded by ``user`` (admins excepted).
        Without this check a user could attach somebody else's file id to their own
        submission and thereby gain access to it. Name and MIME type are taken from
        the database, not from the client.

        Raises:
            HTTPException: 422 when any file is unknown or not owned by the caller
                (same message for both, so ids cannot be probed).
        """
        if not refs:
            return []
        wanted = {ref.file_id for ref in refs}
        found = {f.id: f for f in (await self.db.scalars(select(File).where(File.id.in_(wanted)))).all()}
        resolved: list[dict[str, Any]] = []
        for ref in refs:
            file = found.get(ref.file_id)
            if file is None or (file.uploader_id != user.id and user.role != UserRole.ADMIN):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, f"Attachment {ref.file_id} not found"
                )
            resolved.append(
                {"file_id": str(file.id), "name": file.original_name, "mime_type": file.mime_type}
            )
        return resolved

    async def is_referenced(self, file_id: uuid.UUID) -> bool:
        """True when the file is attached to any assignment, material or submission."""
        needle = _needle(file_id)
        for model in (Assignment, Material, Submission):
            hit = await self.db.scalar(
                select(model.id).where(model.attachments.contains(needle)).limit(1)
            )
            if hit is not None:
                return True
        return False

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #
    async def delete(self, user: User, file_id: uuid.UUID) -> None:
        """Delete a file (uploader only).

        Raises:
            HTTPException: 404 unknown / invisible, 403 visible but not yours,
                409 still attached to content.
        """
        file = await self.db.get(File, file_id)
        if file is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
        if file.uploader_id != user.id:
            if await self.can_access(file, user):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, "Only the uploader can delete this file"
                )
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
        if await self.is_referenced(file.id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "File is attached to classroom content. Remove it from there first.",
            )

        backend = self.backend_for(file)
        key = file.path
        await self.db.delete(file)
        await self.db.commit()
        await self._discard(backend, key)

    # ------------------------------------------------------------------ #
    @staticmethod
    async def _discard(backend: StorageBackend, key: str) -> None:
        """Best-effort removal of a stored object (failures are logged, not raised)."""
        try:
            await backend.delete(key)
        except Exception:  # noqa: BLE001 - an orphaned object must never break the request
            logger.exception("Could not delete stored object %s (orphaned)", key)