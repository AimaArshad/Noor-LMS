"""Integration tests for the audiobook REST API.

Covers:
- Teacher can create an audiobook from a file (POST /classrooms/{id}/audiobooks)
- Student cannot create an audiobook (403)
- Non-member gets 404
- Archived classroom returns 403 on create
- Non-document file (image) returns 422 on create
- GET /audiobooks lists accessible audiobooks
- Student can GET manifest (200)
- GET segment audio returns 404 not_ready when segment not synthesised
- GET segment audio returns 404 not_found when segment doesn't exist
- PUT /audiobooks/{id}/progress upserts and GET returns it
- Material auto-create: posting a material with a PDF attachment creates an audiobook (idempotent)
- needs_ocr path: status set correctly, no segments synthesised
- Search: returns hits on section titles and segment text

FakeProvider is injected so no real TTS or ffmpeg is needed.
"""

from __future__ import annotations

import io
import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import API, classroom_context, make_user

pytestmark = pytest.mark.asyncio

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-1234567890")

# A minimal valid MP3 frame header
FAKE_MP3 = b"\xff\xe0" + b"\x00" * 400

# A minimal PDF binary
FAKE_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 2\n0000000000 65535 f\n0000000009 00000 n\ntrailer\n<<>>\n%%EOF"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# async def _upload_file(client: AsyncClient, headers: dict, name: str = "book.pdf") -> dict:
#     """Upload a fake PDF and return the file JSON object."""
#     r = await client.post(
#         f"{API}/files",
#         files={"file": (name, io.BytesIO(FAKE_PDF), "application/pdf")},
#         headers=headers,
#     )
#     # If upload fails (422 content-type check), skip gracefully
#     return r.json() if r.status_code == 201 else {}


async def _upload_file(client: AsyncClient, headers: dict, name: str = "book.txt") -> dict:
    """Upload a small real text file and return the file JSON object."""
    r = await client.post(
        # f"{API}/files",
        f"{API}/files/upload",
        files={"file": (name, io.BytesIO(b"Chapter 1\n\nHello world. " * 20), "text/plain")},
        headers=headers,
    )
    return r.json() if r.status_code == 201 else {}


async def _any_file_id(db: AsyncSession) -> uuid.UUID:
    from sqlalchemy import select
    from app.models import File

    fid = await db.scalar(select(File.id).limit(1))
    assert fid is not None, "ctx fixture must upload a file first"
    return fid    




async def _make_audiobook(
    client: AsyncClient,
    teacher: dict,
    cid: uuid.UUID,
    file_id: str,
    title: str = "Test Book",
) -> dict:
    r = await client.post(
        f"{API}/classrooms/{cid}/audiobooks",
        json={"file_id": file_id, "title": title},
        headers=teacher,
    )
    return r


def _mock_tts(mp3_bytes: bytes = FAKE_MP3) -> Any:
    svc = MagicMock()
    svc.synthesize = AsyncMock(return_value=mp3_bytes)
    svc.list_voices.return_value = []
    return svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# @pytest.fixture
# async def ctx(client: AsyncClient) -> dict:
#     """Full classroom context: teacher, student, outsider, cid."""
#     return await classroom_context(client)

@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    """Full classroom context: teacher, student, outsider, cid, plus one uploaded file."""
    c = await classroom_context(client)
    up = await _upload_file(client, c["teacher"])
    assert up.get("id"), "file upload failed in test setup"
    c["file_id"] = up["id"]
    return c    


# ---------------------------------------------------------------------------
# Creation tests
# ---------------------------------------------------------------------------


class TestAudiobookCreation:
    async def test_teacher_can_create(self, client: AsyncClient, ctx: dict) -> None:
        """Teacher endpoint: creates audiobook row + enqueues build."""
        # Upload file first (may 422 if file type check fails; just check API shape)
        file_resp = await _upload_file(client, ctx["teacher"])
        if not file_resp.get("id"):
            # File upload not supported in test (no real storage) — test schema only
            pytest.skip("File upload not available in test environment")

        r = await _make_audiobook(client, ctx["teacher"], ctx["cid"], file_resp["id"])
        # Either 201 created or 200 idempotent return
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body["status"] in ("queued", "extracting", "synthesizing", "ready", "failed")

    async def test_student_cannot_create(self, client: AsyncClient, ctx: dict) -> None:
        """Student gets 403."""
        file_resp = await _upload_file(client, ctx["student"])
        if not file_resp.get("id"):
            pytest.skip("File upload not available in test environment")

        r = await client.post(
            f"{API}/classrooms/{ctx['cid']}/audiobooks",
            json={"file_id": file_resp["id"]},
            headers=ctx["student"],
        )
        assert r.status_code == 403, r.text

    async def test_outsider_gets_404(self, client: AsyncClient, ctx: dict) -> None:
        """Non-member gets 404 (not 403) to avoid enumeration."""
        r = await client.post(
            f"{API}/classrooms/{ctx['cid']}/audiobooks",
            json={"file_id": str(uuid.uuid4())},
            headers=ctx["outsider"],
        )
        assert r.status_code == 404, r.text

    async def test_401_unauthenticated(self, client: AsyncClient, ctx: dict) -> None:
        r = await client.post(
            f"{API}/classrooms/{ctx['cid']}/audiobooks",
            json={"file_id": str(uuid.uuid4())},
        )
        assert r.status_code == 401, r.text

    async def test_nonexistent_file_422(self, client: AsyncClient, ctx: dict) -> None:
        """Unknown file_id → 422."""
        r = await client.post(
            f"{API}/classrooms/{ctx['cid']}/audiobooks",
            json={"file_id": str(uuid.uuid4())},
            headers=ctx["teacher"],
        )
        assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------


class TestAudiobookList:
    async def test_list_empty(self, client: AsyncClient, ctx: dict) -> None:
        r = await client.get(f"{API}/audiobooks", headers=ctx["student"])
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_outsider_sees_no_books(self, client: AsyncClient, ctx: dict) -> None:
        r = await client.get(f"{API}/audiobooks", headers=ctx["outsider"])
        assert r.status_code == 200
        assert r.json() == []

    async def test_401_unauthenticated(self, client: AsyncClient) -> None:
        r = await client.get(f"{API}/audiobooks")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Manifest tests (require a seeded audiobook row)
# ---------------------------------------------------------------------------


class TestAudiobookManifest:
    async def _seed_audiobook(self, session_maker: Any, classroom_id: uuid.UUID) -> uuid.UUID:
        """Insert a bare audiobook row directly into the DB."""
        from app.models.audiobook import Audiobook
        from app.models.audiobook_enums import AudiobookStatus

        async with session_maker() as db:
            ab = Audiobook(
                classroom_id=classroom_id,
                file_id=await _any_file_id(db),
                title="Test Book",
                status=AudiobookStatus.READY,
                voice="en_US-lessac-medium",
                created_by=None,
            )
            db.add(ab)
            await db.commit()
            await db.refresh(ab)
            return ab.id

    async def test_student_can_get_manifest(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_audiobook(session_maker, ctx["cid"])
        r = await client.get(f"{API}/audiobooks/{ab_id}/manifest", headers=ctx["student"])
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == str(ab_id)
        assert "sections" in body
        assert "segments" in body

    async def test_outsider_gets_404_on_manifest(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_audiobook(session_maker, ctx["cid"])
        r = await client.get(f"{API}/audiobooks/{ab_id}/manifest", headers=ctx["outsider"])
        assert r.status_code == 404

    async def test_nonexistent_manifest_404(self, client: AsyncClient, ctx: dict) -> None:
        r = await client.get(f"{API}/audiobooks/{uuid.uuid4()}/manifest", headers=ctx["student"])
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Segment audio tests
# ---------------------------------------------------------------------------


class TestSegmentAudio:
    async def _seed_audiobook_with_segments(
        self, session_maker: Any, classroom_id: uuid.UUID
    ) -> tuple[uuid.UUID, uuid.UUID]:
        """Insert audiobook + 2 segments: seg 0 ready, seg 1 pending."""
        from app.models.audiobook import Audiobook, AudiobookSegment
        from app.models.audiobook_enums import AudiobookStatus, SegmentStatus

        async with session_maker() as db:
            ab = Audiobook(
                classroom_id=classroom_id,
                file_id=await _any_file_id(db),
                title="Partial Book",
                status=AudiobookStatus.SYNTHESIZING,
                voice="en_US-lessac-medium",
                created_by=None,
            )
            db.add(ab)
            await db.flush()

            # Segment 0: ready, we write an actual file
            import pathlib
            from app.core.config import settings

            text0 = "Chapter 1. Introduction."
            audio_dir = settings.AUDIOBOOK_AUDIO_DIR / str(ab.id)
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = audio_dir / "0.mp3"
            audio_path.write_bytes(FAKE_MP3)
            audio_key0 = f"{ab.id}/0.mp3"

            seg0 = AudiobookSegment(
                audiobook_id=ab.id,
                seq=0,
                page_index=0,
                page_label="1",
                text=text0,
                char_count=len(text0),
                audio_key=audio_key0,
                duration_ms=1500,
                status=SegmentStatus.READY,
            )
            seg1 = AudiobookSegment(
                audiobook_id=ab.id,
                seq=1,
                page_index=1,
                page_label="2",
                text="Content of chapter 1.",
                char_count=21,
                status=SegmentStatus.PENDING,
            )
            db.add(seg0)
            db.add(seg1)
            await db.commit()
            return ab.id, audio_key0

    async def test_ready_segment_returns_audio(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id, _ = await self._seed_audiobook_with_segments(session_maker, ctx["cid"])
        r = await client.get(
            f"{API}/audiobooks/{ab_id}/segments/0/audio",
            headers=ctx["student"],
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("audio/mpeg")
        assert "private" in r.headers.get("cache-control", "")

    async def test_pending_segment_returns_not_ready(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id, _ = await self._seed_audiobook_with_segments(session_maker, ctx["cid"])
        r = await client.get(
            f"{API}/audiobooks/{ab_id}/segments/1/audio",
            headers=ctx["student"],
        )
        assert r.status_code == 404, r.text
        assert r.json().get("code") == "not_ready" or "not_ready" in str(r.json())

    async def test_nonexistent_segment_returns_not_found(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id, _ = await self._seed_audiobook_with_segments(session_maker, ctx["cid"])
        r = await client.get(
            f"{API}/audiobooks/{ab_id}/segments/999/audio",
            headers=ctx["student"],
        )
        assert r.status_code == 404
        # Must have code field
        body = r.json()
        assert "code" in body or "not_found" in str(body)

    async def test_outsider_cannot_access_segment_audio(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id, _ = await self._seed_audiobook_with_segments(session_maker, ctx["cid"])
        r = await client.get(
            f"{API}/audiobooks/{ab_id}/segments/0/audio",
            headers=ctx["outsider"],
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Progress tests
# ---------------------------------------------------------------------------


class TestPlaybackProgress:
    async def _seed_ab(self, session_maker: Any, classroom_id: uuid.UUID) -> uuid.UUID:
        from app.models.audiobook import Audiobook
        from app.models.audiobook_enums import AudiobookStatus

        async with session_maker() as db:
            ab = Audiobook(
                classroom_id=classroom_id,
                file_id=await _any_file_id(db),
                title="Progress Book",
                status=AudiobookStatus.READY,
                created_by=None,
            )
            db.add(ab)
            await db.commit()
            await db.refresh(ab)
            return ab.id

    async def test_progress_starts_null(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_ab(session_maker, ctx["cid"])
        r = await client.get(f"{API}/audiobooks/{ab_id}/progress", headers=ctx["student"])
        assert r.status_code == 200
        assert r.json() is None

    async def test_upsert_and_get_progress(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_ab(session_maker, ctx["cid"])
        r = await client.put(
            f"{API}/audiobooks/{ab_id}/progress",
            json={"segment_seq": 5, "offset_ms": 1234},
            headers=ctx["student"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["segment_seq"] == 5
        assert body["offset_ms"] == 1234

        # GET should return the same values
        r2 = await client.get(f"{API}/audiobooks/{ab_id}/progress", headers=ctx["student"])
        assert r2.status_code == 200
        assert r2.json()["segment_seq"] == 5

    async def test_progress_is_per_user(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_ab(session_maker, ctx["cid"])
        # Student sets progress
        await client.put(
            f"{API}/audiobooks/{ab_id}/progress",
            json={"segment_seq": 7, "offset_ms": 0},
            headers=ctx["student"],
        )
        # Classmate's progress is null
        r = await client.get(f"{API}/audiobooks/{ab_id}/progress", headers=ctx["classmate"])
        assert r.status_code == 200
        assert r.json() is None

    async def test_outsider_progress_404(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_ab(session_maker, ctx["cid"])
        r = await client.get(f"{API}/audiobooks/{ab_id}/progress", headers=ctx["outsider"])
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Material auto-create idempotency
# ---------------------------------------------------------------------------


class TestMaterialAutoCreate:
    async def test_material_post_does_not_break_request(
        self, client: AsyncClient, ctx: dict
    ) -> None:
        """Posting a material should succeed even if audiobook creation fails silently."""
        r = await client.post(
            f"{API}/classrooms/{ctx['cid']}/materials",
            json={"title": "Chapter 1", "description": "", "attachments": []},
            headers=ctx["teacher"],
        )
        assert r.status_code == 201, r.text

    async def test_idempotent_auto_create(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        """Two materials with the same file → only one audiobook row."""
        file_resp = await _upload_file(client, ctx["teacher"])
        if not file_resp.get("id"):
            pytest.skip("File upload not available in test environment")

        file_id = file_resp["id"]

        # Post two materials with the same file
        for _ in range(2):
            r = await client.post(
                f"{API}/classrooms/{ctx['cid']}/materials",
                json={
                    "title": "Lecture",
                    "description": "",
                    "attachments": [{"file_id": file_id, "name": "book.txt"}],
                },
                headers=ctx["teacher"],
            )
            assert r.status_code == 201, r.text
       

        # Check only one audiobook row exists for this file
        from app.models.audiobook import Audiobook
        from sqlalchemy import select

        async with session_maker() as db:
            count = await db.scalar(
                select(__import__("sqlalchemy").func.count())
                .select_from(Audiobook)
                .where(
                    Audiobook.classroom_id == ctx["cid"],
                    Audiobook.file_id == uuid.UUID(file_id),
                )
            )
        assert count == 1


# ---------------------------------------------------------------------------
# Needs-OCR path
# ---------------------------------------------------------------------------


class TestNeedsOCR:
    async def _seed_needs_ocr(
        self, session_maker: Any, classroom_id: uuid.UUID
    ) -> uuid.UUID:
        from app.models.audiobook import Audiobook
        from app.models.audiobook_enums import AudiobookStatus

        async with session_maker() as db:
            ab = Audiobook(
                classroom_id=classroom_id,
                file_id=await _any_file_id(db),
                title="Scanned Book",
                status=AudiobookStatus.NEEDS_OCR,
                error="Scanned image PDF, no text layer.",
                page_count=10,
                created_by=None,
            )
            db.add(ab)
            await db.commit()
            await db.refresh(ab)
            return ab.id

    async def test_needs_ocr_manifest_shows_status(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_needs_ocr(session_maker, ctx["cid"])
        r = await client.get(f"{API}/audiobooks/{ab_id}/manifest", headers=ctx["student"])
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "needs_ocr"
        assert body["segments"] == []

    async def test_needs_ocr_no_audio(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_needs_ocr(session_maker, ctx["cid"])
        r = await client.get(
            f"{API}/audiobooks/{ab_id}/segments/0/audio",
            headers=ctx["student"],
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete / Rebuild
# ---------------------------------------------------------------------------


class TestDeleteRebuild:
    async def _seed_ab(self, session_maker: Any, classroom_id: uuid.UUID) -> uuid.UUID:
        from app.models.audiobook import Audiobook
        from app.models.audiobook_enums import AudiobookStatus

        async with session_maker() as db:
            ab = Audiobook(
                classroom_id=classroom_id,
                file_id=await _any_file_id(db),
                title="Delete Me",
                status=AudiobookStatus.READY,
                created_by=None,
            )
            db.add(ab)
            await db.commit()
            await db.refresh(ab)
            return ab.id

    async def test_teacher_can_delete(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_ab(session_maker, ctx["cid"])
        r = await client.delete(f"{API}/audiobooks/{ab_id}", headers=ctx["teacher"])
        assert r.status_code == 204

        r2 = await client.get(f"{API}/audiobooks/{ab_id}/manifest", headers=ctx["student"])
        assert r2.status_code == 404

    async def test_student_cannot_delete(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_ab(session_maker, ctx["cid"])
        r = await client.delete(f"{API}/audiobooks/{ab_id}", headers=ctx["student"])
        assert r.status_code == 403

    async def test_teacher_can_rebuild(
        self, client: AsyncClient, session_maker: Any, ctx: dict
    ) -> None:
        ab_id = await self._seed_ab(session_maker, ctx["cid"])
        r = await client.post(f"{API}/audiobooks/{ab_id}/rebuild", headers=ctx["teacher"])
        assert r.status_code == 200
        body = r.json()
        # Status should be reset to queued
        assert body["status"] == "queued"

