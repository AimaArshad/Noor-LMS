"""Audiobook Celery task: extract structure → synthesise segments.

Task name: ``audiobook.build``

Pipeline
--------
1. Load the audiobook row; mark ``status = extracting``.
2. Read the source file bytes from the local storage backend directly.
3. Run ``extract_structure()`` synchronously (it uses asyncio.to_thread internally;
   we call it via asyncio.run to get a new event loop for each task).
4. If status == needs_ocr → set ``status = needs_ocr`` with a human message, stop.
5. Delete stale sections/segments, insert fresh ones (idempotent rebuild).
6. Mark ``status = synthesizing``.
7. For each segment in order, synthesise with TTSService via asyncio.run;
   store ``audio_key`` and ``duration_ms``; mark segment ``ready`` immediately
   so playback can start before the book finishes.
8. When all done: set ``total_duration_ms`` and ``status = ready``.

PageTextSource interface
------------------------
``PageTextSource`` is a callable ``(page_index: int) → str``.  The pipeline uses
the extracted page text by default.  An OCR adapter can be dropped in later by
passing a different callable to the pipeline without touching this file.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import pathlib
import uuid
import wave

from celery import Task
from celery.utils.log import get_task_logger

from app.worker.celery_app import celery_app

task_logger = get_task_logger("educonnect.audiobook_tasks")

# ---------------------------------------------------------------------------
# DB session helper (synchronous)
# ---------------------------------------------------------------------------

_SyncSessionFactory = None


def _get_sync_session():  # noqa: ANN202
    """Return a synchronous SQLAlchemy session (new each time)."""
    global _SyncSessionFactory  # noqa: PLW0603
    if _SyncSessionFactory is None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.core.config import settings

        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        engine = create_engine(sync_url, pool_pre_ping=True, pool_size=2, max_overflow=4)
        _SyncSessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return _SyncSessionFactory()


# ---------------------------------------------------------------------------
# TTS cache helpers (mirror TTSService logic exactly)
# ---------------------------------------------------------------------------

def _tts_cache_key(text: str, voice: str, provider: str) -> str:
    raw = f"{provider}|{voice}|{text}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _tts_cache_path(key: str) -> pathlib.Path:
    from app.core.config import settings

    return settings.TTS_CACHE_DIR / key[:2] / f"{key}.mp3"


# ---------------------------------------------------------------------------
# MP3 duration estimation
# ---------------------------------------------------------------------------

def _mp3_duration_ms(mp3_bytes: bytes) -> int:
    """Estimate MP3 duration in milliseconds from bitrate and size."""
    _BITRATE = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
    for i in range(min(len(mp3_bytes) - 3, 8192)):
        if mp3_bytes[i] != 0xFF or (mp3_bytes[i + 1] & 0xE0) != 0xE0:
            continue
        br_idx = (mp3_bytes[i + 2] >> 4) & 0x0F
        sr_idx = (mp3_bytes[i + 2] >> 2) & 0x03
        bitrate = _BITRATE[br_idx] * 1000
        sr_table = [44100, 48000, 32000, 0]
        samplerate = sr_table[sr_idx]
        if bitrate and samplerate:
            return int(len(mp3_bytes) * 8 / bitrate * 1000)
    return int(len(mp3_bytes) * 8 / 128000 * 1000)


# ---------------------------------------------------------------------------
# File reading (sync, direct filesystem access)
# ---------------------------------------------------------------------------

def _read_file_bytes(path: pathlib.Path) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _extract_book(file_bytes: bytes, mime_type: str):  # noqa: ANN202
    """Run extract_structure in a fresh event loop (sync entry point)."""
    from app.services.structure_extraction import extract_structure

    return asyncio.run(extract_structure(file_bytes, mime_type))


def _synthesise_text(text: str, voice: str) -> bytes:
    """Synthesise one text segment and return MP3 bytes.

    Checks the TTS disk cache first (same key logic as TTSService), so
    re-runs of the pipeline do not re-generate already-cached audio.
    Uses a fresh event loop per call (safe in a sync Celery worker).
    """
    from app.services.tts_service import TTSService, build_providers

    tts = TTSService(providers=build_providers())
    return asyncio.run(tts.synthesize(text, voice=voice))


# ---------------------------------------------------------------------------
# Main pipeline (synchronous)
# ---------------------------------------------------------------------------

def _build_audiobook_sync(audiobook_id_str: str) -> None:  # noqa: C901, PLR0912, PLR0915
    """Synchronous pipeline body called from the Celery task."""
    from app.core.config import settings
    from app.models.audiobook import Audiobook, AudiobookSection, AudiobookSegment
    from app.models.audiobook_enums import AudiobookStatus, SegmentStatus
    from app.models.file import File
    from app.services.segmenter import SegmentDraft, build_segments
    from app.services.structure_extraction import ExtractionError
    from app.services.tts_service import TTSProviderError

    ab_id = uuid.UUID(audiobook_id_str)
    db = _get_sync_session()

    try:
        ab: Audiobook | None = db.get(Audiobook, ab_id)
        if ab is None:
            task_logger.error("Audiobook %s not found in DB", ab_id)
            return

        # 1. Mark extracting
        ab.status = AudiobookStatus.EXTRACTING
        db.commit()

        # 2. Read file bytes
        file_obj: File | None = db.get(File, ab.file_id)
        if file_obj is None:
            ab.status = AudiobookStatus.FAILED
            ab.error = "Source file has been deleted"
            db.commit()
            return

        file_path = settings.STORAGE_DIR / file_obj.path
        try:
            file_bytes = _read_file_bytes(file_path)
        except Exception as exc:  # noqa: BLE001
            ab.status = AudiobookStatus.FAILED
            ab.error = f"Could not read source file: {exc}"
            db.commit()
            return

        # 3. Extract structure
        try:
            book = _extract_book(file_bytes, file_obj.mime_type)
        except ExtractionError as exc:
            ab.status = AudiobookStatus.FAILED
            ab.error = str(exc)[:500]
            db.commit()
            return
        except Exception as exc:  # noqa: BLE001
            ab.status = AudiobookStatus.FAILED
            ab.error = f"Extraction error: {exc}"[:500]
            db.commit()
            raise

        # 4. needs_ocr?
        if book.status == "needs_ocr":
            ab.status = AudiobookStatus.NEEDS_OCR
            ab.error = (
                "This document appears to be a scanned image PDF with no selectable text. "
                "OCR support is not yet available."
            )
            ab.page_count = len(book.pages)
            db.commit()
            return

        # 5. Insert sections + segments (delete stale data first for idempotency)
        db.query(AudiobookSegment).filter(
            AudiobookSegment.audiobook_id == ab_id
        ).delete(synchronize_session=False)
        db.query(AudiobookSection).filter(
            AudiobookSection.audiobook_id == ab_id
        ).delete(synchronize_session=False)
        db.commit()

        all_segs: list[SegmentDraft] = build_segments(book)

        # Build section_id_map: section_index → new UUID
        section_id_map: dict[int, uuid.UUID] = {}
        for sec_idx, sec in enumerate(book.sections):
            sec_id = uuid.uuid4()
            section_id_map[sec_idx] = sec_id

            end_page: int | None = None
            if sec_idx + 1 < len(book.sections):
                end_page = book.sections[sec_idx + 1].start_page - 1

            first_seq: int | None = None
            last_seq: int | None = None
            for sd in all_segs:
                if sd.section_index == sec_idx:
                    if first_seq is None:
                        first_seq = sd.seq
                    last_seq = sd.seq

            parent_id: uuid.UUID | None = None
            if sec.level > 1:
                for prev_idx in range(sec_idx - 1, -1, -1):
                    if book.sections[prev_idx].level < sec.level:
                        parent_id = section_id_map.get(prev_idx)
                        break

            db.add(AudiobookSection(
                id=sec_id,
                audiobook_id=ab_id,
                seq=sec_idx,
                parent_id=parent_id,
                level=sec.level,
                number=sec.number,
                title=sec.title,
                title_norm=sec.title.lower(),
                start_page=sec.start_page,
                end_page=end_page,
                first_segment_seq=first_seq,
                last_segment_seq=last_seq,
            ))
        db.commit()

        # Insert segment rows (all pending initially)
        for sd in all_segs:
            sec_id = section_id_map.get(sd.section_index) if sd.section_index is not None else None
            db.add(AudiobookSegment(
                audiobook_id=ab_id,
                seq=sd.seq,
                section_id=sec_id,
                page_index=sd.page_index,
                page_label=sd.page_label,
                text=sd.text,
                char_count=sd.char_count,
                status=SegmentStatus.PENDING,
            ))

        ab.page_count = len(book.pages)
        ab.pages_approximate = getattr(book, "pages_are_approximate", False)
        db.commit()

        # 6. Mark synthesizing
        ab.status = AudiobookStatus.SYNTHESIZING
        db.commit()

        # 7. Synthesise in order
        voice = ab.voice or settings.PIPER_DEFAULT_VOICE
        db_segs = (
            db.query(AudiobookSegment)
            .filter(AudiobookSegment.audiobook_id == ab_id)
            .order_by(AudiobookSegment.seq)
            .all()
        )

        for db_seg in db_segs:
            # Idempotent: skip if already ready AND cache file exists
            if db_seg.status == SegmentStatus.READY and db_seg.audio_key:
                p = _tts_cache_path(db_seg.audio_key)
                if p.is_file():
                    continue

            try:
                mp3_bytes = _synthesise_text(db_seg.text, voice)
            except TTSProviderError as exc:
                db_seg.status = SegmentStatus.FAILED
                db.commit()
                if exc.transient:
                    raise  # allow Celery to retry
                continue  # permanent failure: skip this segment

            # Determine audio_key (piper is preferred provider)
            audio_key = _tts_cache_key(db_seg.text, voice, "piper")
            duration = _mp3_duration_ms(mp3_bytes)

            db_seg.audio_key = audio_key
            db_seg.duration_ms = duration
            db_seg.status = SegmentStatus.READY
            db.commit()
            task_logger.debug("Segment %d synthesised (%d ms)", db_seg.seq, duration)

        # 8. Finalize
        ready_segs = (
            db.query(AudiobookSegment)
            .filter(
                AudiobookSegment.audiobook_id == ab_id,
                AudiobookSegment.status == SegmentStatus.READY,
            )
            .all()
        )
        total_ms = sum(s.duration_ms or 0 for s in ready_segs)
        ab.total_duration_ms = total_ms
        ab.status = AudiobookStatus.READY
        db.commit()
        task_logger.info(
            "Audiobook %s READY: %d segments, %d ms",
            ab_id, len(ready_segs), total_ms,
        )

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(
    name="audiobook.build",
    bind=True,
    max_retries=3,
    acks_late=True,
)
def build_audiobook(self: Task, audiobook_id: str) -> None:
    """Celery entry point: build an audiobook from a source file."""
    task_logger.info("audiobook.build starting: %s", audiobook_id)
    try:
        _build_audiobook_sync(audiobook_id)
    except Exception as exc:  # noqa: BLE001
        from app.services.tts_service import TTSProviderError

        if isinstance(exc, TTSProviderError) and exc.transient:
            backoff = 60 * (2 ** self.request.retries)
            task_logger.warning("Transient TTS error; retrying in %ds: %s", backoff, exc)
            raise self.retry(exc=exc, countdown=backoff) from exc

        # Permanent or unknown error: mark failed, don't retry
        try:
            db = _get_sync_session()
            try:
                from app.models.audiobook import Audiobook
                from app.models.audiobook_enums import AudiobookStatus

                ab = db.get(Audiobook, uuid.UUID(audiobook_id))
                if ab is not None:
                    ab.status = AudiobookStatus.FAILED
                    ab.error = str(exc)[:500]
                    db.commit()
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            pass
        raise
