"""Audiobook business-logic service.

Responsibilities
----------------
* Create / upsert audiobook rows (idempotent per classroom+file).
* Delete an audiobook and its cached audio files.
* Build the GET /audiobooks list (across classrooms the caller belongs to).
* Build the manifest response (outline tree + segment list + progress).
* Upsert / fetch playback progress.
* Full-text + trigram search within an audiobook.

The heavy pipeline work (extraction → synthesis) is done by the Celery task
``audiobook.build`` in ``app/worker/audiobook_tasks.py``.
"""

from __future__ import annotations

import logging
import pathlib
import shutil
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    Audiobook,
    AudiobookSection,
    AudiobookSegment,
    Classroom,
    ClassroomMember,
    File,
    PlaybackProgress,
    User,
)
from app.models.audiobook_enums import AudiobookStatus, SegmentStatus
from app.schemas.audiobooks import (
    AudiobookCreate,
    AudiobookListItem,
    AudiobookManifest,
    PlaybackProgressRead,
    PlaybackProgressUpdate,
    SearchHit,
    SectionNode,
    SegmentInfo,
)
from app.worker.dispatch import enqueue

logger = logging.getLogger("educonnect.audiobooks")

# MIME types that may be turned into audiobooks
AUDIOBOOK_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ab_audio_dir(ab_id: uuid.UUID) -> pathlib.Path:
    """Directory that holds all synthesised MP3s for one audiobook."""
    return settings.AUDIOBOOK_AUDIO_DIR / str(ab_id)


# def _resolve_audio_path(audio_key: str) -> pathlib.Path:
#     """Resolve relative ``audio_key`` against AUDIOBOOK_AUDIO_DIR.

#     Rejects path traversal attempts (e.g. ``../../etc/passwd``).
#     Raises ``ValueError`` if the resolved path escapes the base directory.
#     """
#     base = settings.AUDIOBOOK_AUDIO_DIR.resolve()
#     p = (base / audio_key).resolve()
#     if not str(p).startswith(str(base) + ("/" if str(base)[-1] != "/" else "")):
#         raise ValueError(f"Path traversal rejected: {audio_key!r}")
#     return p

def _resolve_audio_path(audio_key: str) -> pathlib.Path:
    """Resolve relative ``audio_key`` against AUDIOBOOK_AUDIO_DIR.

    Rejects path traversal attempts (e.g. ``../../etc/passwd``).
    Raises ``ValueError`` if the resolved path escapes the base directory.
    """
    base = pathlib.Path(settings.AUDIOBOOK_AUDIO_DIR).resolve()
    p = (base / audio_key).resolve()
    if not p.is_relative_to(base):          # works on Windows and Linux
        raise ValueError(f"Path traversal rejected: {audio_key!r}")
    return p

# ---------------------------------------------------------------------------
# AudiobookService
# ---------------------------------------------------------------------------

class AudiobookService:
    """Stateless per-request service."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _get_audiobook(self, audiobook_id: uuid.UUID) -> Audiobook:
        ab = await self.db.get(Audiobook, audiobook_id)
        if ab is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Audiobook not found")
        return ab

    async def _assert_member(self, audiobook: Audiobook, user: User) -> ClassroomMember | None:
        """Return the membership row (or None for admins); raise 404 if not a member."""
        from app.models import UserRole

        if user.role == UserRole.ADMIN:
            return None
        member = await self.db.scalar(
            select(ClassroomMember).where(
                ClassroomMember.classroom_id == audiobook.classroom_id,
                ClassroomMember.user_id == user.id,
            )
        )
        if member is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Audiobook not found")
        return member

    async def _assert_teacher_access(self, audiobook: Audiobook, user: User) -> None:
        """Raise 403 when caller is a student; 404 when not a member."""
        from app.models import MemberRole, UserRole

        if user.role == UserRole.ADMIN:
            return
        member = await self._assert_member(audiobook, user)
        if member is not None and member.role != MemberRole.TEACHER:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only classroom teachers can do this")

    # ------------------------------------------------------------------ #
    # Creation
    # ------------------------------------------------------------------ #

    async def _resolve_file(
        self, file_id: uuid.UUID, user: User, classroom: Classroom
    ) -> File:
        """Load and validate a file for audiobook creation.

        Rules (teacher endpoint):
        - File must exist and have been uploaded by this teacher.
        - MIME must be PDF / DOCX / TXT.
        - Classroom must not be archived.
        """
        from app.services.guards import ensure_not_archived

        ensure_not_archived(classroom.is_archived)
        file: File | None = await self.db.get(File, file_id)
        if file is None or file.uploader_id != user.id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "File not found or not uploaded by you",
            )
        if file.mime_type not in AUDIOBOOK_MIMES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Only PDF, DOCX and TXT files can be turned into audiobooks",
            )
        return file

    async def _upsert_audiobook(
        self,
        classroom: Classroom,
        file: File,
        title: str | None,
        created_by: uuid.UUID,
        *,
        voice: str | None = None,
    ) -> tuple[Audiobook, bool]:
        """Idempotent insert of an audiobook row.

        Returns (audiobook, created: bool).
        A second call for the same classroom+file returns the existing row
        without modifying it (idempotent for the auto-create path).
        """
        existing = await self.db.scalar(
            select(Audiobook).where(
                Audiobook.classroom_id == classroom.id,
                Audiobook.file_id == file.id,
            )
        )
        if existing is not None:
            return existing, False

        ab_title = title or file.original_name
        ab = Audiobook(
            classroom_id=classroom.id,
            file_id=file.id,
            title=ab_title,
            status=AudiobookStatus.QUEUED,
            voice=voice or settings.PIPER_DEFAULT_VOICE,
            created_by=created_by,
        )
        self.db.add(ab)
        await self.db.flush()  # assigns ab.id
        await self.db.commit()
        await self.db.refresh(ab)
        return ab, True

    async def create(
        self,
        classroom: Classroom,
        user: User,
        data: AudiobookCreate,
    ) -> Audiobook:
        """Teacher endpoint: create + enqueue.  Returns the new Audiobook row."""
        file = await self._resolve_file(data.file_id, user, classroom)
        ab, created = await self._upsert_audiobook(
            classroom, file, data.title, created_by=user.id
        )
        if created:
            task_id = enqueue("audiobook.build", str(ab.id))
            if task_id is None:
                ab.status = AudiobookStatus.FAILED
                ab.error = "Could not enqueue build task (broker unavailable)"
                await self.db.commit()
                await self.db.refresh(ab)
        return ab

    async def auto_create_from_material(
        self,
        classroom: Classroom,
        file_id: uuid.UUID,
        file_mime: str,
        created_by: uuid.UUID,
        *,
        file_name: str = "",
    ) -> None:
        """Called from MaterialService after a successful material create/update.

        Idempotent: if an audiobook already exists for this classroom+file, does nothing.
        The MIME type is read from the stored file row (``file_mime`` is kept only for
        call-site compatibility and is ignored).
        enqueue() never raises, so this never fails the HTTP request.
        """
        file: File | None = await self.db.get(File, file_id)
        if file is None or file.mime_type not in AUDIOBOOK_MIMES:
            return
        ab, created = await self._upsert_audiobook(
            classroom, file, file_name or file.original_name, created_by
        )
        if created:
            enqueue("audiobook.build", str(ab.id))

    # ------------------------------------------------------------------ #
    # Rebuild / Delete
    # ------------------------------------------------------------------ #

    async def rebuild(self, audiobook_id: uuid.UUID, user: User) -> Audiobook:
        from app.services.guards import ensure_not_archived

        ab = await self._get_audiobook(audiobook_id)
        classroom = await self.db.get(Classroom, ab.classroom_id)
        if classroom is not None:
            ensure_not_archived(classroom.is_archived)
        await self._assert_teacher_access(ab, user)

        # 409 if the build is already in progress
        _IN_PROGRESS = {AudiobookStatus.QUEUED, AudiobookStatus.EXTRACTING, AudiobookStatus.SYNTHESIZING}
        if ab.status in _IN_PROGRESS:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Audiobook build is already in progress (status: {ab.status.value})",
            )

        # Clear any previously synthesised audio so the worker starts fresh
        shutil.rmtree(_ab_audio_dir(ab.id), ignore_errors=True)
        ab.status = AudiobookStatus.QUEUED
        ab.error = None
        await self.db.commit()
        task_id = enqueue("audiobook.build", str(ab.id))
        if task_id is None:
            ab.status = AudiobookStatus.FAILED
            ab.error = "Could not enqueue build task (broker unavailable)"
            await self.db.commit()
        await self.db.refresh(ab)
        return ab

    async def delete(self, audiobook_id: uuid.UUID, user: User) -> None:
        from app.services.guards import ensure_not_archived

        ab = await self._get_audiobook(audiobook_id)
        classroom = await self.db.get(Classroom, ab.classroom_id)
        if classroom is not None:
            ensure_not_archived(classroom.is_archived)
        await self._assert_teacher_access(ab, user)

        # Best-effort delete of the whole audio directory for this book
        shutil.rmtree(_ab_audio_dir(ab.id), ignore_errors=True)

        await self.db.delete(ab)
        await self.db.commit()

    # ------------------------------------------------------------------ #
    # Read: list
    # ------------------------------------------------------------------ #

    async def list_accessible(
        self,
        user: User,
        *,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AudiobookListItem]:
        """Return all audiobooks the caller can access across classrooms."""
        from app.models import UserRole

        if user.role == UserRole.ADMIN:
            # Admins see everything
            stmt = select(Audiobook, Classroom.name).join(
                Classroom, Classroom.id == Audiobook.classroom_id
            )
        else:
            stmt = (
                select(Audiobook, Classroom.name)
                .join(Classroom, Classroom.id == Audiobook.classroom_id)
                .join(
                    ClassroomMember,
                    and_(
                        ClassroomMember.classroom_id == Audiobook.classroom_id,
                        ClassroomMember.user_id == user.id,
                    ),
                )
            )

        if q:
            stmt = stmt.where(Audiobook.title.ilike(f"%{q}%"))

        stmt = stmt.order_by(Audiobook.created_at.desc()).limit(limit).offset(offset)
        rows = (await self.db.execute(stmt)).all()

        # Fetch progress for all returned audiobooks in one query
        ab_ids = [row[0].id for row in rows]
        progress_rows = (
            await self.db.execute(
                select(PlaybackProgress).where(
                    PlaybackProgress.user_id == user.id,
                    PlaybackProgress.audiobook_id.in_(ab_ids),
                )
            )
        ).scalars().all()
        progress_by_id = {p.audiobook_id: p for p in progress_rows}

        items: list[AudiobookListItem] = []
        for ab, classroom_name in rows:
            # Compute progress %
            prog_pct: float | None = None
            if ab.page_count and ab.page_count > 0:
                prog = progress_by_id.get(ab.id)
                if prog is not None:
                    # rough: segment_seq / total_segments
                    total_segs = await self.db.scalar(
                        select(func.count()).select_from(AudiobookSegment)
                        .where(AudiobookSegment.audiobook_id == ab.id)
                    ) or 1
                    prog_pct = round(prog.segment_seq / total_segs * 100, 1)
            items.append(
                AudiobookListItem(
                    id=ab.id,
                    title=ab.title,
                    classroom_name=classroom_name,
                    status=ab.status,
                    error=ab.error,
                    progress_pct=prog_pct,
                    page_count=ab.page_count,
                )
            )
        return items

    # ------------------------------------------------------------------ #
    # Read: manifest
    # ------------------------------------------------------------------ #

    async def get_manifest(
        self, audiobook_id: uuid.UUID, user: User
    ) -> AudiobookManifest:
        ab = await self._get_audiobook(audiobook_id)
        await self._assert_member(ab, user)

        sections = (
            await self.db.scalars(
                select(AudiobookSection)
                .where(AudiobookSection.audiobook_id == ab.id)
                .order_by(AudiobookSection.seq)
            )
        ).all()
        segments = (
            await self.db.scalars(
                select(AudiobookSegment)
                .where(AudiobookSegment.audiobook_id == ab.id)
                .order_by(AudiobookSegment.seq)
            )
        ).all()
        progress = await self.db.scalar(
            select(PlaybackProgress).where(
                PlaybackProgress.user_id == user.id,
                PlaybackProgress.audiobook_id == ab.id,
            )
        )

        section_nodes = [
            SectionNode(
                id=sec.id,
                seq=sec.seq,
                parent_id=sec.parent_id,
                level=sec.level,
                number=sec.number,
                title=sec.title,
                start_page=sec.start_page,
                end_page=sec.end_page,
                first_segment_seq=sec.first_segment_seq,
                last_segment_seq=sec.last_segment_seq,
            )
            for sec in sections
        ]

        segment_infos = [
            SegmentInfo(
                seq=seg.seq,
                section_id=seg.section_id,
                page_label=seg.page_label,
                duration_ms=seg.duration_ms,
                status=seg.status,
            )
            for seg in segments
        ]

        prog_read: PlaybackProgressRead | None = None
        if progress is not None:
            prog_read = PlaybackProgressRead(
                segment_seq=progress.segment_seq,
                offset_ms=progress.offset_ms,
                updated_at=progress.updated_at,
            )

        total_segs = len(segments)
        ready_segs = sum(1 for s in segments if s.status == SegmentStatus.READY)
        manifest_progress_pct: float | None = None
        if total_segs > 0:
            manifest_progress_pct = round(ready_segs / total_segs * 100, 1)

        return AudiobookManifest(
            id=ab.id,
            title=ab.title,
            status=ab.status,
            error=ab.error,
            page_count=ab.page_count,
            total_duration_ms=ab.total_duration_ms,
            progress_pct=manifest_progress_pct,
            sections=section_nodes,
            segments=segment_infos,
            progress=prog_read,
        )

    # ------------------------------------------------------------------ #
    # Segment audio
    # ------------------------------------------------------------------ #

    async def get_segment_audio_path(
        self, audiobook_id: uuid.UUID, seq: int, user: User
    ) -> pathlib.Path:
        """Return the filesystem path to the cached MP3, with access checks.

        Raises:
            HTTPException 404 (not_found): audiobook / segment unknown.
            HTTPException 404 (not_ready): segment exists but audio not ready.
        """
        ab = await self._get_audiobook(audiobook_id)
        await self._assert_member(ab, user)

        seg = await self.db.scalar(
            select(AudiobookSegment).where(
                AudiobookSegment.audiobook_id == ab.id,
                AudiobookSegment.seq == seq,
            )
        )
        if seg is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"code": "not_found", "message": "Segment not found"},
            )
        if seg.status != SegmentStatus.READY or not seg.audio_key:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"code": "not_ready", "message": "Segment audio is not ready yet"},
            )

        try:
            p = _resolve_audio_path(seg.audio_key)
        except ValueError:
            # raise HTTPException(
            #     status.HTTP_404_NOT_FOUND,
            #     detail={"code": "not_found", "message": "Segment not found"},
            # )
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"code": "not_found", "message": "Invalid audio path"},
            )
        if not p.is_file():
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"code": "not_ready", "message": "Segment audio is not ready yet"},
            )
        return p

    # ------------------------------------------------------------------ #
    # Progress
    # ------------------------------------------------------------------ #

    async def get_progress(
        self, audiobook_id: uuid.UUID, user: User
    ) -> PlaybackProgressRead | None:
        ab = await self._get_audiobook(audiobook_id)
        await self._assert_member(ab, user)
        prog = await self.db.scalar(
            select(PlaybackProgress).where(
                PlaybackProgress.user_id == user.id,
                PlaybackProgress.audiobook_id == ab.id,
            )
        )
        if prog is None:
            return None
        return PlaybackProgressRead(
            segment_seq=prog.segment_seq,
            offset_ms=prog.offset_ms,
            updated_at=prog.updated_at,
        )

    async def upsert_progress(
        self,
        audiobook_id: uuid.UUID,
        user: User,
        data: PlaybackProgressUpdate,
    ) -> PlaybackProgressRead:
        ab = await self._get_audiobook(audiobook_id)
        await self._assert_member(ab, user)
        await self.db.execute(
            text("""
                INSERT INTO playback_progress (user_id, audiobook_id, segment_seq, offset_ms, updated_at)
                VALUES (:uid, :abid, :seq, :off, now())
                ON CONFLICT (user_id, audiobook_id) DO UPDATE
                    SET segment_seq = EXCLUDED.segment_seq,
                        offset_ms   = EXCLUDED.offset_ms,
                        updated_at  = now()
            """),
            {"uid": user.id, "abid": ab.id, "seq": data.segment_seq, "off": data.offset_ms},
        )
        await self.db.commit()
        prog = await self.db.scalar(
            select(PlaybackProgress).where(
                PlaybackProgress.user_id == user.id,
                PlaybackProgress.audiobook_id == ab.id,
            )
        )
        assert prog is not None  # just inserted
        return PlaybackProgressRead(
            segment_seq=prog.segment_seq,
            offset_ms=prog.offset_ms,
            updated_at=prog.updated_at,
        )

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    async def search(
        self, audiobook_id: uuid.UUID, user: User, q: str
    ) -> list[SearchHit]:
        ab = await self._get_audiobook(audiobook_id)
        await self._assert_member(ab, user)

        if not q.strip():
            return []

        # 1) Trigram match on section titles (ranked first)
        section_hits = (
            await self.db.execute(
                text("""
                    SELECT
                        s.id          AS section_id,
                        s.title       AS section_title,
                        NULL          AS segment_seq,
                        NULL          AS page_label,
                        s.title       AS snippet,
                        1.0           AS rank
                    FROM audiobook_sections s
                    WHERE s.audiobook_id = :abid
                      AND s.title_norm ILIKE :pat
                    ORDER BY rank DESC
                    LIMIT 10
                """),
                {"abid": ab.id, "pat": f"%{q}%"},
            )
        ).mappings().all()

        # 2) Full-text search on segment bodies.
        # plainto_tsquery accepts any user text safely (to_tsquery raises on ' : & ! ( ) ).
        seg_hits = (
            await self.db.execute(
                text("""
                    SELECT
                        seg.section_id,
                        sec.title       AS section_title,
                        seg.seq         AS segment_seq,
                        seg.page_label,
                        ts_headline('english', seg.text,
                                    plainto_tsquery('english', :tq),
                                    'MaxWords=15,MinWords=5') AS snippet,
                        ts_rank(to_tsvector('english', seg.text),
                                plainto_tsquery('english', :tq))   AS rank
                    FROM audiobook_segments seg
                    LEFT JOIN audiobook_sections sec ON sec.id = seg.section_id
                    WHERE seg.audiobook_id = :abid
                      AND to_tsvector('english', seg.text) @@ plainto_tsquery('english', :tq)
                    ORDER BY rank DESC
                    LIMIT 20
                """),
                {"abid": ab.id, "tq": q},
            )
        ).mappings().all()

        hits: list[SearchHit] = []
        for row in list(section_hits) + list(seg_hits):
            hits.append(
                SearchHit(
                    section_id=row["section_id"],
                    section_title=row["section_title"],
                    segment_seq=row["segment_seq"],
                    page_label=row["page_label"],
                    snippet=row["snippet"],
                    rank=float(row["rank"]),
                )
            )
        return hits
