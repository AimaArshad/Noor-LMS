"""``build_segments`` — split an ``ExtractedBook`` into TTS-ready segments.

Design
------
* Target 800-1500 characters per segment; hard max is the page char cap (2000).
* Segments never cross page boundaries.
* Segments never cross section-heading boundaries.
* A special *announcement* segment is prepended at each section start:
  "Chapter 2. Kinetic theory." so the listener knows which chapter they are in.
* Sentence boundary splitting uses a simple regex (no NLTK needed); it handles
  common abbreviations (Mr., Dr., e.g., i.e., Fig., ...) well enough for TTS.

Data classes
-----------
``SegmentDraft`` — an ordered segment not yet associated with a DB row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.structure_extraction import ExtractedBook, Page, Section

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_MIN = 800   # preferred minimum chars per segment
TARGET_MAX = 1500  # preferred maximum chars per segment; never exceeded for page-splits

# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class SegmentDraft:
    """An ordered TTS segment, not yet stored in the DB."""

    seq: int           # 0-based global order
    section_index: int | None  # index into book.sections (None = preamble / no section)
    page_index: int    # page this segment starts on
    page_label: str    # printed label of that page
    text: str          # text to synthesize
    char_count: int = field(init=False)
    is_announcement: bool = False  # True for "Chapter N. Title." segments

    def __post_init__(self) -> None:
        self.char_count = len(self.text)


# ---------------------------------------------------------------------------
# Sentence splitter
# ---------------------------------------------------------------------------

# End of sentence: .!? followed by whitespace and an uppercase letter or digit,
# but NOT if the period is part of an abbreviation like "Mr.", "e.g.", "Fig. 2".
_SENT_SPLIT_RE = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z\d])"
)

# Common abbreviations that should NOT trigger a sentence split
_ABBREV_SET = frozenset([
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr",
    "vs", "etc", "i.e", "e.g", "fig", "eq", "no",
    "vol", "ch", "approx", "dept",
])


def _split_sentences(text: str) -> list[str]:
    """Split ``text`` into sentences without using NLTK.

    Heuristic: split at sentence-ending punctuation followed by whitespace and
    an uppercase letter, but protect common abbreviations.
    """
    # First do a naive split
    candidates = _SENT_SPLIT_RE.split(text)
    merged: list[str] = []
    for c in candidates:
        if merged:
            # Check if the end of the previous sentence is an abbreviation
            prev = merged[-1].rstrip()
            last_word = re.search(r"\b(\w+)\.$", prev)
            if last_word and last_word.group(1).lower() in _ABBREV_SET:
                merged[-1] = merged[-1] + " " + c
                continue
        merged.append(c)
    return [s.strip() for s in merged if s.strip()]


# ---------------------------------------------------------------------------
# Core segmenter
# ---------------------------------------------------------------------------


def _make_announcement(section: Section) -> str:
    """Build the spoken announcement for a section heading."""
    prefix = {1: "Chapter", 2: "Topic", 3: "Sub-topic"}.get(section.level, "Section")
    num_str = f" {section.number}" if section.number is not None else ""
    return f"{prefix}{num_str}. {section.title}."


def _section_at_page(sections: list[Section], page_index: int) -> int | None:
    """Return the index of the latest section that starts on or before ``page_index``."""
    result: int | None = None
    for i, sec in enumerate(sections):
        if sec.start_page <= page_index:
            result = i
        else:
            break
    return result


def _pack_into_segments(
    texts: list[str],
    section_index: int | None,
    page_index: int,
    page_label: str,
    seq_start: int,
) -> list[SegmentDraft]:
    """Greedily pack sentences into segments of TARGET_MIN–TARGET_MAX chars."""
    segments: list[SegmentDraft] = []
    buf: list[str] = []
    buf_len = 0
    seq = seq_start

    for sentence in texts:
        sentence_len = len(sentence)
        if buf and buf_len + sentence_len + 1 > TARGET_MAX:
            # Flush current buffer
            segments.append(SegmentDraft(
                seq=seq,
                section_index=section_index,
                page_index=page_index,
                page_label=page_label,
                text=" ".join(buf),
            ))
            seq += 1
            buf = []
            buf_len = 0

        buf.append(sentence)
        buf_len += sentence_len + 1

        # Also flush when we've reached the target minimum
        if buf_len >= TARGET_MIN:
            segments.append(SegmentDraft(
                seq=seq,
                section_index=section_index,
                page_index=page_index,
                page_label=page_label,
                text=" ".join(buf),
            ))
            seq += 1
            buf = []
            buf_len = 0

    if buf:
        segments.append(SegmentDraft(
            seq=seq,
            section_index=section_index,
            page_index=page_index,
            page_label=page_label,
            text=" ".join(buf),
        ))

    return segments


def build_segments(book: ExtractedBook) -> list[SegmentDraft]:
    """Convert an ``ExtractedBook`` into an ordered list of TTS segments.

    Rules:
    - Segments never cross page boundaries.
    - Segments never cross section-heading boundaries.
    - A spoken announcement is inserted at each section's first page.
    - Each segment targets 800-1500 characters (never padded, may be shorter
      if a page has little text).

    Args:
        book: The result of ``extract_structure``.

    Returns:
        Ordered list of :class:`SegmentDraft` objects ready for DB insertion.
    """
    all_segments: list[SegmentDraft] = []
    seq = 0

    # Build a lookup: page_index → list of section indices that start there
    page_to_sections: dict[int, list[int]] = {}
    for idx, sec in enumerate(book.sections):
        page_to_sections.setdefault(sec.start_page, []).append(idx)

    # Track current section
    current_section_idx: int | None = None

    # With at least two chapters, nothing before the first chapter is read aloud
    # (cover, credits, contents). Page numbers and indexes are unchanged.
    level1_pages = sorted(s.start_page for s in book.sections if s.level == 1)
    first_chapter_page = level1_pages[0] if len(level1_pages) >= 2 else None

    for page in book.pages:
        page_idx = page.index
        if first_chapter_page is not None and page_idx < first_chapter_page:
            continue
        page_text = page.text.strip()

        # --- Insert announcements for sections starting on this page --- #
        for sec_idx in page_to_sections.get(page_idx, []):
            sec = book.sections[sec_idx]
            announcement = _make_announcement(sec)
            all_segments.append(SegmentDraft(
                seq=seq,
                section_index=sec_idx,
                page_index=page_idx,
                page_label=page.label,
                text=announcement,
                is_announcement=True,
            ))
            seq += 1
            current_section_idx = sec_idx

        # --- Skip empty pages --- #
        if not page_text:
            continue

        # --- Determine section for this page (if no section started here) --- #
        section_idx = current_section_idx
        # Update if a section started on a later page (shouldn't happen but be safe)
        if page_to_sections.get(page_idx):
            section_idx = page_to_sections[page_idx][-1]

        # --- Split page text into sentences then pack into segments --- #
        sentences = _split_sentences(page_text)
        if not sentences:
            # Fallback: treat entire page text as one segment
            all_segments.append(SegmentDraft(
                seq=seq,
                section_index=section_idx,
                page_index=page_idx,
                page_label=page.label,
                text=page_text[:TARGET_MAX],
            ))
            seq += 1
            continue

        page_segs = _pack_into_segments(
            sentences,
            section_idx,
            page_idx,
            page.label,
            seq,
        )
        for s in page_segs:
            s.seq = seq
            seq += 1
        all_segments.extend(page_segs)

    return all_segments

