"""Voice command resolution: parse text → look up DB → build response.

Responsibilities
----------------
* Parse the transcript with ``voice_parser.parse_command``.
* Resolve book/section targets from the parsed params using the audiobooks
  the caller can access (via ``AudiobookService.list_accessible``).
* Use ``rapidfuzz`` for fuzzy title matching.
* Build a human-readable ``speech`` sentence for screen-reader playback.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Audiobook,
    AudiobookSection,
    AudiobookSegment,
    Classroom,
    ClassroomMember,
    User,
)
from app.models.audiobook_enums import AudiobookStatus, SegmentStatus
from app.schemas.voice import VoiceCommandResponse, VoiceTarget
from app.services.voice_parser import Command, parse_command

logger = logging.getLogger("educonnect.voice_command")

# rapidfuzz is optional-soft: if missing, fall back to plain substring
try:
    from rapidfuzz import fuzz as _fuzz

    def _score(a: str, b: str) -> float:
        return _fuzz.token_set_ratio(a.lower(), b.lower())

except ImportError:  # pragma: no cover
    logger.warning("rapidfuzz not installed; falling back to substring matching")

    def _score(a: str, b: str) -> float:  # type: ignore[misc]
        a_l, b_l = a.lower(), b.lower()
        if a_l in b_l or b_l in a_l:
            return 90.0
        return 0.0


_FUZZY_THRESHOLD = 60.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _accessible_audiobooks(
    db: AsyncSession, user: User
) -> list[tuple[Audiobook, str]]:
    """Return list of (Audiobook, classroom_name) the user can access."""
    from app.models import UserRole

    if user.role == UserRole.ADMIN:
        stmt = (
            select(Audiobook, Classroom.name)
            .join(Classroom, Classroom.id == Audiobook.classroom_id)
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

    rows = (await db.execute(stmt)).all()
    return [(ab, name) for ab, name in rows]


def _best_book_match(
    hint: str | None,
    class_hint: str | None,
    books: list[tuple[Audiobook, str]],
    pinned_id: uuid.UUID | None,
) -> Audiobook | None:
    """Pick the best matching audiobook.

    Priority:
    1. Pinned audiobook_id (from request body) if supplied.
    2. Fuzzy match on title + classroom_name using hint / class_hint.
    3. If no hint at all and there is exactly one audiobook, return it.
    """
    if pinned_id is not None:
        for ab, _name in books:
            if ab.id == pinned_id:
                return ab
        return None

    if not hint and not class_hint:
        # No hint: single book is unambiguous
        if len(books) == 1:
            return books[0][0]
        return None

    query = " ".join(filter(None, [hint, class_hint])).strip()

    best_ab: Audiobook | None = None
    best_score = _FUZZY_THRESHOLD - 1

    for ab, classroom_name in books:
        candidate = f"{ab.title} {classroom_name}"
        score = _score(query, candidate)
        if score > best_score:
            best_score = score
            best_ab = ab

    return best_ab


async def _resolve_chapter(
    db: AsyncSession, ab: Audiobook, chapter_num: int | None
) -> AudiobookSection | None:
    """Find the level-1 section with the given chapter number."""
    stmt = select(AudiobookSection).where(
        AudiobookSection.audiobook_id == ab.id,
        AudiobookSection.level == 1,
    )
    if chapter_num is not None:
        stmt = stmt.where(AudiobookSection.number == chapter_num)
    stmt = stmt.order_by(AudiobookSection.seq)
    return await db.scalar(stmt)


async def _resolve_topic(
    db: AsyncSession, ab: Audiobook, topic: str
) -> AudiobookSection | None:
    """Find the best matching section by title (all levels)."""
    sections = (
        await db.scalars(
            select(AudiobookSection)
            .where(AudiobookSection.audiobook_id == ab.id)
            .order_by(AudiobookSection.seq)
        )
    ).all()

    best: AudiobookSection | None = None
    best_score = _FUZZY_THRESHOLD - 1

    for sec in sections:
        score = _score(topic, sec.title)
        if score > best_score:
            best_score = score
            best = sec

    return best


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------

async def resolve_voice_command(
    text: str,
    db: AsyncSession,
    user: User,
    audiobook_id: uuid.UUID | None,
) -> VoiceCommandResponse:
    """Parse *text*, look up DB, return a structured response."""
    cmd: Command = parse_command(text)
    intent = cmd.intent
    params = cmd.params

    books = await _accessible_audiobooks(db, user)

    # --- Intents that don't need a book target ---
    if intent == "help":
        return VoiceCommandResponse(
            intent=intent,
            action="show_help",
            target=VoiceTarget(),
            speech=(
                "Here are some commands you can say: "
                "play, pause, stop, resume, "
                "forward thirty seconds, backward thirty seconds, "
                "go to chapter one, go to page five, "
                "play topic introduction, "
                "next chapter, previous chapter, "
                "where am I, faster, slower."
            ),
        )

    if intent == "unknown":
        return VoiceCommandResponse(
            intent=intent,
            action="none",
            target=VoiceTarget(),
            speech="Sorry, I didn't understand that command. Say 'help' for a list of commands.",
        )

    # Simple playback intents (no book needed if audiobook_id supplied)
    if intent in ("play", "pause", "stop", "resume", "where_am_i", "faster", "slower"):
        ab = _best_book_match(None, None, books, audiobook_id)
        target = VoiceTarget(audiobook_id=ab.id if ab else None)
        speech_map = {
            "play": "Playing.",
            "pause": "Paused.",
            "stop": "Stopped.",
            "resume": "Resuming.",
            "where_am_i": "Fetching your current position.",
            "faster": "Speed increased.",
            "slower": "Speed decreased.",
        }
        return VoiceCommandResponse(
            intent=intent,
            action=intent,
            target=target,
            speech=speech_map[intent],
        )

    if intent in ("forward", "backward"):
        ab = _best_book_match(None, None, books, audiobook_id)
        seconds = params.get("seconds", 30)
        direction = "forward" if intent == "forward" else "backward"
        return VoiceCommandResponse(
            intent=intent,
            action=intent,
            target=VoiceTarget(audiobook_id=ab.id if ab else None),
            speech=f"Skipping {direction} {seconds} seconds.",
        )

    if intent in ("next_chapter", "previous_chapter"):
        ab = _best_book_match(None, None, books, audiobook_id)
        label = "next" if intent == "next_chapter" else "previous"
        return VoiceCommandResponse(
            intent=intent,
            action=intent,
            target=VoiceTarget(audiobook_id=ab.id if ab else None),
            speech=f"Going to {label} chapter.",
        )

    # --- Intents that resolve a book + section ---
    if intent == "go_chapter":
        chapter_num = params.get("chapter")
        book_hint = params.get("book")
        class_hint = params.get("class_hint")

        ab = _best_book_match(book_hint, class_hint, books, audiobook_id)
        if ab is None:
            hint_text = " ".join(filter(None, [book_hint, class_hint])) or "the book"
            return VoiceCommandResponse(
                intent=intent,
                action="none",
                target=VoiceTarget(),
                speech=f"I could not find {hint_text}. Please open an audiobook first.",
            )

        if ab.status not in (AudiobookStatus.READY, AudiobookStatus.SYNTHESIZING):
            return VoiceCommandResponse(
                intent=intent,
                action="none",
                target=VoiceTarget(audiobook_id=ab.id),
                speech=f"The audiobook '{ab.title}' is not ready yet.",
            )

        sec = await _resolve_chapter(db, ab, chapter_num)
        if sec is None:
            ch_label = f"chapter {chapter_num}" if chapter_num else "that chapter"
            return VoiceCommandResponse(
                intent=intent,
                action="none",
                target=VoiceTarget(audiobook_id=ab.id),
                speech=f"I could not find {ch_label} in '{ab.title}'.",
            )

        # Check segment readiness
        if sec.first_segment_seq is not None:
            seg = await db.scalar(
                select(AudiobookSegment).where(
                    AudiobookSegment.audiobook_id == ab.id,
                    AudiobookSegment.seq == sec.first_segment_seq,
                )
            )
            if seg is not None and seg.status != SegmentStatus.READY:
                return VoiceCommandResponse(
                    intent=intent,
                    action="none",
                    target=VoiceTarget(audiobook_id=ab.id, section_seq=sec.seq),
                    speech="This chapter is still being prepared.",
                )

        return VoiceCommandResponse(
            intent=intent,
            action="seek_section",
            target=VoiceTarget(
                audiobook_id=ab.id,
                section_seq=sec.seq,
                segment_seq=sec.first_segment_seq,
                page=sec.start_page,
            ),
            speech=f"Going to {sec.title} in '{ab.title}'.",
        )

    if intent == "go_page":
        page_num = params.get("page")
        book_hint = params.get("book")

        ab = _best_book_match(book_hint, None, books, audiobook_id)
        if ab is None:
            hint_text = book_hint or "the book"
            return VoiceCommandResponse(
                intent=intent,
                action="none",
                target=VoiceTarget(),
                speech=f"I could not find {hint_text}. Please open an audiobook first.",
            )

        # Find first segment whose page_index matches (0-based = page_num - 1)
        target_page = (page_num - 1) if page_num and page_num > 0 else 0
        seg = await db.scalar(
            select(AudiobookSegment)
            .where(
                AudiobookSegment.audiobook_id == ab.id,
                AudiobookSegment.page_index == target_page,
            )
            .order_by(AudiobookSegment.seq)
        )

        page_label = str(page_num) if page_num else "that page"
        if seg is None:
            return VoiceCommandResponse(
                intent=intent,
                action="none",
                target=VoiceTarget(audiobook_id=ab.id),
                speech=f"I could not find page {page_label} in '{ab.title}'.",
            )

        return VoiceCommandResponse(
            intent=intent,
            action="seek_segment",
            target=VoiceTarget(
                audiobook_id=ab.id,
                segment_seq=seg.seq,
                page=target_page,
            ),
            speech=f"Going to page {page_label} in '{ab.title}'.",
        )

    if intent == "play_topic":
        topic = params.get("topic", "")
        book_hint = params.get("book")
        class_hint = params.get("class_hint")

        ab = _best_book_match(book_hint, class_hint, books, audiobook_id)
        if ab is None:
            hint_text = " ".join(filter(None, [book_hint, class_hint])) or "the book"
            return VoiceCommandResponse(
                intent=intent,
                action="none",
                target=VoiceTarget(),
                speech=f"I could not find {hint_text}. Please open an audiobook first.",
            )

        sec = await _resolve_topic(db, ab, topic)
        if sec is None:
            return VoiceCommandResponse(
                intent=intent,
                action="none",
                target=VoiceTarget(audiobook_id=ab.id),
                speech=f"I could not find the topic '{topic}' in '{ab.title}'.",
            )

        return VoiceCommandResponse(
            intent=intent,
            action="seek_section",
            target=VoiceTarget(
                audiobook_id=ab.id,
                section_seq=sec.seq,
                segment_seq=sec.first_segment_seq,
                page=sec.start_page,
            ),
            speech=f"Going to '{sec.title}' in '{ab.title}'.",
        )

    # Fallback (should not happen)
    return VoiceCommandResponse(
        intent=intent,
        action="none",
        target=VoiceTarget(),
        speech="Sorry, I could not process that command.",
    )

