"""Unit tests for the B2 polish (no database needed)."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.build_staleness import is_stale
from app.services.segmenter import build_segments
from app.services.voice_command_service import _best_book_match, _join_hints


# --- 1. stale builds ---------------------------------------------------------

def test_is_stale_thresholds():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert not is_stale(now - timedelta(minutes=29), now)
    assert is_stale(now - timedelta(minutes=31), now)
    assert is_stale(None, now)


def test_is_stale_treats_naive_datetimes_as_utc():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert is_stale(datetime(2026, 1, 1, 11, 0), now)
    assert not is_stale(datetime(2026, 1, 1, 11, 45), now)


# --- 2. voice: hint text and matching ---------------------------------------

def _book(title: str):
    return SimpleNamespace(id=uuid.uuid4(), title=title)


def test_join_hints_does_not_repeat_the_class_hint():
    assert _join_hints("physics 2nd year", "2nd year") == "physics 2nd year"
    assert _join_hints("2nd year", "physics 2nd year") == "physics 2nd year"
    assert _join_hints("physics", "2nd year") == "physics 2nd year"
    assert _join_hints(None, None) == ""


def test_book_match_ignores_case_hyphens_and_spoken_ordinals():
    ab1, ab2 = _book("physics-2nd year"), _book("Chemistry 1st Year")
    books = [(ab1, "Physics 2"), (ab2, "Chemistry 1")]
    assert _best_book_match("Physics Second Year", None, books, None) is ab1
    assert _best_book_match("physics", "2nd year", books, None) is ab1
    assert _best_book_match("chemistry first year", None, books, None) is ab2
    assert _best_book_match("biology", None, books, None) is None


# --- 3. front matter is not synthesised -------------------------------------

TEXT = "This is a sentence about physics. Here is another sentence."


def _page(i):
    return SimpleNamespace(index=i, label=str(i + 1), text=TEXT)


def _sec(level, number, title, start):
    return SimpleNamespace(level=level, number=number, title=title, start_page=start)


def test_front_matter_skipped_when_book_has_two_chapters():
    book = SimpleNamespace(
        pages=[_page(i) for i in range(5)],
        sections=[_sec(1, 1, "One", 2), _sec(1, 2, "Two", 4)],
    )
    segs = build_segments(book)
    assert min(s.page_index for s in segs) == 2          # cover/contents (pages 0-1) skipped
    assert [s.seq for s in segs] == list(range(len(segs)))  # numbering still starts at 0
    assert segs[0].is_announcement                         # first thing heard: "Chapter 1. One."


def test_front_matter_kept_for_a_single_chapter():
    book = SimpleNamespace(pages=[_page(i) for i in range(5)], sections=[_sec(1, 1, "One", 2)])
    segs = build_segments(book)
    assert min(s.page_index for s in segs) == 0
