"""Integration tests for POST /voice/command and POST /voice/transcribe.

Covers:
- 401 when unauthenticated
- 200 with valid command text (all major intents)
- Fuzzy audiobook matching (title / classroom)
- Transcribe endpoint: mocked transcription; 413 on oversize file
"""

from __future__ import annotations

import io
import uuid
from typing import Any
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import API, classroom_context, make_user

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VOICE_API = f"{API}/voice"


async def _upload_file(
    client: AsyncClient,
    headers: dict,
    classroom_id: uuid.UUID,
    content: bytes = b"%PDF-1.4\nThis is a sample PDF document with enough text to pass the extraction threshold. " * 5,
    mime: str = "text/plain",
    filename: str = "test.txt",
) -> uuid.UUID:
    """Upload a file and return its file_id."""
    resp = await client.post(
        f"{API}/files/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), mime)},
        data={"classroom_id": str(classroom_id)},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["id"])


# ---------------------------------------------------------------------------
# 401 / auth guard
# ---------------------------------------------------------------------------


async def test_command_requires_auth(client: AsyncClient) -> None:
    r = await client.post(f"{VOICE_API}/command", json={"text": "play"})
    assert r.status_code == 401


async def test_transcribe_requires_auth(client: AsyncClient) -> None:
    r = await client.post(
        f"{VOICE_API}/transcribe",
        files={"audio": ("a.wav", io.BytesIO(b"\x00" * 10), "audio/wav")},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Simple intents (no book needed)
# ---------------------------------------------------------------------------


async def test_command_help(client: AsyncClient) -> None:
    user = await make_user(client, "voice_help@example.com")
    r = await client.post(f"{VOICE_API}/command", json={"text": "help"}, headers=user)
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "help"
    assert body["action"] == "show_help"
    assert "play" in body["speech"].lower()


async def test_command_unknown(client: AsyncClient) -> None:
    user = await make_user(client, "voice_unk@example.com")
    r = await client.post(f"{VOICE_API}/command", json={"text": "blah blah blah"}, headers=user)
    assert r.status_code == 200
    assert r.json()["intent"] == "unknown"
    assert r.json()["action"] == "none"


async def test_command_pause(client: AsyncClient) -> None:
    user = await make_user(client, "voice_pause@example.com")
    r = await client.post(f"{VOICE_API}/command", json={"text": "pause"}, headers=user)
    assert r.status_code == 200
    assert r.json()["intent"] == "pause"


async def test_command_forward_default(client: AsyncClient) -> None:
    user = await make_user(client, "voice_fwd@example.com")
    r = await client.post(f"{VOICE_API}/command", json={"text": "forward"}, headers=user)
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "forward"
    assert "30" in body["speech"]


async def test_command_forward_explicit_seconds(client: AsyncClient) -> None:
    user = await make_user(client, "voice_fwd2@example.com")
    r = await client.post(
        f"{VOICE_API}/command", json={"text": "forward 60 seconds"}, headers=user
    )
    assert r.status_code == 200
    assert "60" in r.json()["speech"]


async def test_command_next_chapter(client: AsyncClient) -> None:
    user = await make_user(client, "voice_nxt@example.com")
    r = await client.post(f"{VOICE_API}/command", json={"text": "next chapter"}, headers=user)
    assert r.status_code == 200
    assert r.json()["intent"] == "next_chapter"


# ---------------------------------------------------------------------------
# go_chapter — no accessible book → graceful "not found" speech
# ---------------------------------------------------------------------------


async def test_go_chapter_no_books(client: AsyncClient) -> None:
    user = await make_user(client, "voice_nob@example.com")
    r = await client.post(
        f"{VOICE_API}/command",
        json={"text": "go to chapter 3 in physics"},
        headers=user,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "go_chapter"
    assert body["action"] == "none"
    assert "physics" in body["speech"].lower() or "not" in body["speech"].lower()


# ---------------------------------------------------------------------------
# go_chapter — with an accessible audiobook
# ---------------------------------------------------------------------------


async def test_go_chapter_resolves_section(
    client: AsyncClient, session_maker: Any
) -> None:
    ctx = await classroom_context(client)
    teacher = ctx["teacher"]
    student = ctx["student"]
    cid: uuid.UUID = ctx["cid"]

    # Seed an audiobook with a chapter section directly in DB
    from app.models.audiobook import Audiobook, AudiobookSection
    from app.models.audiobook_enums import AudiobookStatus

    async with session_maker() as db:
        # We need a file row; use the files upload endpoint
        content = b"Chapter 1 Introduction\n" + (b"Hello world. " * 40)
        fid = await _upload_file(client, teacher, cid, content=content, mime="text/plain")

        ab = Audiobook(
            classroom_id=cid,
            file_id=fid,
            title="Physics Book",
            status=AudiobookStatus.READY,
            voice="en_US-lessac-medium",
            created_by=None,
        )
        db.add(ab)
        await db.flush()

        sec = AudiobookSection(
            audiobook_id=ab.id,
            seq=0,
            level=1,
            number=1,
            title="Introduction",
            title_norm="introduction",
            start_page=0,
            end_page=5,
            first_segment_seq=None,
            last_segment_seq=None,
        )
        db.add(sec)
        await db.commit()
        ab_id = ab.id

    r = await client.post(
        f"{VOICE_API}/command",
        json={"text": "go to chapter 1", "audiobook_id": str(ab_id)},
        headers=student,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "go_chapter"
    assert body["action"] == "seek_section"
    assert body["target"]["audiobook_id"] == str(ab_id)
    assert body["target"]["section_seq"] == 0
    assert "introduction" in body["speech"].lower()


# ---------------------------------------------------------------------------
# play_topic fuzzy match
# ---------------------------------------------------------------------------


async def test_play_topic_resolves(client: AsyncClient, session_maker: Any) -> None:
    ctx = await classroom_context(client)
    teacher = ctx["teacher"]
    student = ctx["student"]
    cid: uuid.UUID = ctx["cid"]

    from app.models.audiobook import Audiobook, AudiobookSection
    from app.models.audiobook_enums import AudiobookStatus

    async with session_maker() as db:
        content = b"Chapter 1 Waves\n" + (b"Wave content. " * 40)
        fid = await _upload_file(client, teacher, cid, content=content, mime="text/plain")
        ab = Audiobook(
            classroom_id=cid,
            file_id=fid,
            title="Physics",
            status=AudiobookStatus.READY,
            voice="en_US-lessac-medium",
            created_by=None,
        )
        db.add(ab)
        await db.flush()
        sec = AudiobookSection(
            audiobook_id=ab.id,
            seq=0,
            level=2,
            number=None,
            title="Waves and Motion",
            title_norm="waves and motion",
            start_page=0,
            end_page=3,
            first_segment_seq=None,
            last_segment_seq=None,
        )
        db.add(sec)
        await db.commit()
        ab_id = ab.id

    r = await client.post(
        f"{VOICE_API}/command",
        json={"text": "play topic waves", "audiobook_id": str(ab_id)},
        headers=student,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "play_topic"
    assert body["action"] == "seek_section"
    assert "waves" in body["speech"].lower()


# ---------------------------------------------------------------------------
# go_page — with accessible audiobook but no matching segment
# ---------------------------------------------------------------------------


async def test_go_page_not_found(client: AsyncClient, session_maker: Any) -> None:
    ctx = await classroom_context(client)
    teacher = ctx["teacher"]
    student = ctx["student"]
    cid: uuid.UUID = ctx["cid"]

    from app.models.audiobook import Audiobook
    from app.models.audiobook_enums import AudiobookStatus

    async with session_maker() as db:
        content = b"Sample text. " * 50
        fid = await _upload_file(client, teacher, cid, content=content, mime="text/plain")
        ab = Audiobook(
            classroom_id=cid,
            file_id=fid,
            title="Math Book",
            status=AudiobookStatus.READY,
            created_by=None,
        )
        db.add(ab)
        await db.commit()
        ab_id = ab.id

    r = await client.post(
        f"{VOICE_API}/command",
        json={"text": "go to page 999", "audiobook_id": str(ab_id)},
        headers=student,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "go_page"
    assert body["action"] == "none"
    assert "999" in body["speech"] or "not" in body["speech"].lower()


# ---------------------------------------------------------------------------
# outsider cannot access another user's audiobook via go_chapter
# ---------------------------------------------------------------------------


async def test_command_outsider_cannot_reach_private_book(
    client: AsyncClient, session_maker: Any
) -> None:
    ctx = await classroom_context(client)
    teacher = ctx["teacher"]
    outsider = ctx["outsider"]
    cid: uuid.UUID = ctx["cid"]

    from app.models.audiobook import Audiobook
    from app.models.audiobook_enums import AudiobookStatus

    async with session_maker() as db:
        content = b"Secret content. " * 50
        fid = await _upload_file(client, teacher, cid, content=content, mime="text/plain")
        ab = Audiobook(
            classroom_id=cid,
            file_id=fid,
            title="Secret Physics",
            status=AudiobookStatus.READY,
            created_by=None,
        )
        db.add(ab)
        await db.commit()
        ab_id = ab.id

    # Outsider uses the ab_id but is not a member of the classroom
    r = await client.post(
        f"{VOICE_API}/command",
        json={"text": "go to chapter 1", "audiobook_id": str(ab_id)},
        headers=outsider,
    )
    assert r.status_code == 200
    body = r.json()
    # Should resolve to "none" because the outsider cannot see the book
    assert body["action"] == "none" or body["target"]["audiobook_id"] is None


# ---------------------------------------------------------------------------
# Transcribe endpoint — mocked
# ---------------------------------------------------------------------------


async def test_transcribe_returns_text(client: AsyncClient) -> None:
    user = await make_user(client, "voice_tr@example.com")

    with patch(
        "app.api.v1.routers.voice._do_transcribe",  # patched at import site
        return_value="go to chapter two",
    ) as mock_tr:
        r = await client.post(
            f"{VOICE_API}/transcribe",
            headers=user,
            files={"audio": ("clip.wav", io.BytesIO(b"\x00" * 100), "audio/wav")},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == "go to chapter two"
    assert body["language"] == "en"


async def test_transcribe_413_on_oversize(client: AsyncClient) -> None:
    user = await make_user(client, "voice_big@example.com")
    big_audio = b"\x00" * (10 * 1024 * 1024 + 1)  # 10 MB + 1 byte

    r = await client.post(
        f"{VOICE_API}/transcribe",
        headers=user,
        files={"audio": ("big.wav", io.BytesIO(big_audio), "audio/wav")},
    )
    assert r.status_code == 413


async def test_transcribe_422_on_empty(client: AsyncClient) -> None:
    user = await make_user(client, "voice_empty@example.com")
    r = await client.post(
        f"{VOICE_API}/transcribe",
        headers=user,
        files={"audio": ("empty.wav", io.BytesIO(b""), "audio/wav")},
    )
    assert r.status_code == 422


async def test_transcribe_503_on_model_failure(client: AsyncClient) -> None:
    user = await make_user(client, "voice_fail@example.com")

    with patch(
        "app.api.v1.routers.voice._do_transcribe",
        side_effect=RuntimeError("model not found"),
    ):
        r = await client.post(
            f"{VOICE_API}/transcribe",
            headers=user,
            files={"audio": ("clip.wav", io.BytesIO(b"\x00" * 100), "audio/wav")},
        )
    assert r.status_code == 503
