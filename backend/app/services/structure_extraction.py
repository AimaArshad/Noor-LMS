"""``extract_structure`` — parse PDF/DOCX/TXT into structured pages + sections.

Design
------
* Pure functions; heavy imports are deferred (lazy) so the module loads fast.
* All document work runs in a thread (via ``asyncio.to_thread``) in the router.
* The 100 000-char cap is gone; individual pages are capped at 2000 chars.
* OCR detection: a document whose pages are mostly image-only is flagged as
  ``status="needs_ocr"`` without attempting synthesis.

Data classes
-----------
``Page``       — physical or synthetic page with index, printed label, and text.
``Section``    — chapter/topic heading with level, number, title, start page.
``ExtractedBook`` — container returned by ``extract_structure``.

PDF strategy (in order of preference)
--------------------------------------
1. Outline (bookmarks) → map destinations to page numbers.
2. Heuristic heading detection per page (regex patterns).
3. No sections — pages only.

DOCX strategy
-------------
Heading 1/2/3 → level 1/2/3 sections; explicit page-break paragraphs create
real page boundaries; otherwise synthetic pages of ~1800 chars.

TXT/Markdown strategy
---------------------
``# Heading`` / ``Chapter N`` / ``## Sub`` → sections; synthetic pages.

Running headers/footers
-----------------------
Lines present on more than 30 % of pages are stripped. Bare page numbers
(a line that is only a number) are stripped.

TOC detection
-------------
Lines containing dot leaders ("….. 5" or "... 12") are skipped.

Chapter number parsing
----------------------
"Chapter 2" → 2; "Part II" → 2; "Chapter Two" → 2.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

PAGE_CHAR_CAP = 2000  # maximum characters stored per page

class ExtractionError(Exception):
    """Raised when a document cannot be turned into readable text."""

@dataclass
class Page:
    """One physical (PDF) or synthetic (DOCX/TXT) page."""

    index: int             # 0-based position in document
    label: str             # printed label, e.g. "iv", "1", "A-3"
    text: str              # up to PAGE_CHAR_CAP chars


@dataclass
class Section:
    """A chapter, topic or sub-topic heading."""

    level: int             # 1 = chapter, 2 = topic, 3 = sub-topic
    number: int | None     # parsed integer (None if un-numbered)
    title: str             # heading text (cleaned)
    start_page: int        # 0-based page index where heading appears
    text_offset: int       # char offset within the page (best effort)


@dataclass
class ExtractedBook:
    pages: list[Page]
    sections: list[Section]
    status: Literal["ok", "needs_ocr"]
    pages_are_approximate: bool = False


# ---------------------------------------------------------------------------
# Chapter number helpers
# ---------------------------------------------------------------------------

_WORD_NUMBERS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}
_ROMAN: dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
}


def _parse_chapter_number(raw: str) -> int | None:
    """Parse a chapter number from arabic, roman or word form."""
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    if raw.upper() in _ROMAN:
        return _ROMAN[raw.upper()]
    if raw.lower() in _WORD_NUMBERS:
        return _WORD_NUMBERS[raw.lower()]
    return None


# Heading detection patterns, in priority order.
# Groups: (prefix_keyword, number_token, title_text)  — only some capture groups
_HEADING_PATTERNS: list[tuple[int, re.Pattern]] = [
    # "Chapter 3", "Chapter III", "Chapter Three"
    (1, re.compile(
        r"^\s*(?:chapter|chap\.?|part|unit|module|section|lesson)\s+"
        r"(?P<num>[IVXLCDM]+|\d+|[A-Za-z]+)"
        r"(?:[:\.\s]+(?P<title>.+))?$",
        re.IGNORECASE,
    )),
    # "3.1 Title" or "3.1.2 Title"
    (2, re.compile(
        r"^\s*(?P<num>\d+\.\d+(?:\.\d+)*)\s+(?P<title>[A-Z].{3,})$"
    )),
    # "3. Title" (top-level numbered)
    (1, re.compile(
        r"^\s*(?P<num>\d+)\.\s+(?P<title>[A-Z].{3,})$"
    )),
]

# Short ALL-CAPS line that looks like a heading (not a running header)
_ALLCAPS_RE = re.compile(r"^[A-Z][A-Z0-9 \-:,\.]{3,60}$")

# TOC line detector (dot leaders or lots of periods before a number)
_TOC_LINE_RE = re.compile(r"\.{3,}\s*\d+\s*$|…+\s*\d+\s*$")

# Bare page number line
_BARE_NUMBER_RE = re.compile(r"^\s*\d{1,4}\s*$")


def _is_toc_line(line: str) -> bool:
    return bool(_TOC_LINE_RE.search(line))


def _is_bare_number(line: str) -> bool:
    return bool(_BARE_NUMBER_RE.match(line))


def _strip_running_headers(pages_text: list[str], threshold: float = 0.30) -> list[str]:
    """Remove lines repeated on more than ``threshold`` fraction of pages."""
    if not pages_text:
        return pages_text
    # Build frequency map for each unique single-line string
    line_count: dict[str, int] = {}
    for text in pages_text:
        seen = set()
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and stripped not in seen:
                seen.add(stripped)
                line_count[stripped] = line_count.get(stripped, 0) + 1
    n = len(pages_text)
    running = {ln for ln, cnt in line_count.items() if cnt / n > threshold}

    cleaned: list[str] = []
    for text in pages_text:
        lines = [
            ln for ln in text.splitlines()
            if ln.strip() not in running
            and not _is_bare_number(ln.strip())
            and not _is_toc_line(ln)
        ]
        cleaned.append("\n".join(lines))
    return cleaned


# ---------------------------------------------------------------------------
# Heading detection from raw page text
# ---------------------------------------------------------------------------

def _detect_heading(line: str) -> tuple[int, int | None, str] | None:
    """Return (level, number, title) if ``line`` looks like a heading, else None."""
    for level, pat in _HEADING_PATTERNS:
        m = pat.match(line.strip())
        if m:
            d = m.groupdict()
            raw_num = d.get("num", "")
            # For dotted numbers like "3.1", use the first component
            num_part = raw_num.split(".")[0] if "." in raw_num else raw_num
            number = _parse_chapter_number(num_part)
            title = (d.get("title") or line.strip()).strip()
            return (level, number, title)
    # Short ALL-CAPS line heuristic
    stripped = line.strip()
    if _ALLCAPS_RE.match(stripped) and len(stripped) > 4:
        return (1, None, stripped.title())
    return None


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def _extract_pdf(data: bytes) -> ExtractedBook:
    """Extract structure from a PDF using pypdf."""
    # Deferred import — only paid when actually processing a PDF
    from pypdf import PdfReader  # type: ignore[import-untyped]
    from pypdf.generic import Destination  # type: ignore[import-untyped]
    import io

    reader = PdfReader(io.BytesIO(data))
    n = len(reader.pages)

    # ---- Page labels --------------------------------------------------- #
    labels: list[str] = []
    try:
        raw_labels = list(reader.page_labels)
        for i in range(n):
            labels.append(raw_labels[i] if i < len(raw_labels) else str(i + 1))
    except Exception:
        labels = [str(i + 1) for i in range(n)]

    # ---- Raw text extraction ------------------------------------------- #
    raw_texts: list[str] = []
    for pg in reader.pages:
        try:
            raw_texts.append(pg.extract_text() or "")
        except Exception:
            raw_texts.append("")

    # ---- OCR detection ------------------------------------------------- #
    nonempty = sum(1 for t in raw_texts if t.strip())
    needs_ocr = nonempty < max(1, n * 0.5)

    # ---- Strip headers/footers ---------------------------------------- #
    cleaned_texts = _strip_running_headers(raw_texts)

    # ---- Build Page objects -------------------------------------------- #
    pages: list[Page] = [
        Page(
            index=i,
            label=labels[i],
            text=cleaned_texts[i][:PAGE_CHAR_CAP],
        )
        for i in range(n)
    ]

    # ---- Sections from outline (bookmarks) ----------------------------- #
    sections: list[Section] = []
    try:
        outline = reader.outline
        if outline:
            sections = _pdf_outline_to_sections(reader, outline, pages)
    except Exception:
        outline = None

    # ---- Fallback: heuristic heading detection ------------------------- #
    if not sections:
        sections = _pdf_heuristic_sections(pages)

    return ExtractedBook(
        pages=pages,
        sections=sections,
        status="needs_ocr" if needs_ocr else "ok",
    )


def _pdf_dest_to_page(reader, dest) -> int:
    """Resolve a pypdf Destination to a 0-based page index."""
    try:
        # pypdf ≥ 4: dest.page is a PageObject we can look up
        for i, pg in enumerate(reader.pages):
            if pg.indirect_reference == dest.page.indirect_reference:
                return i
    except Exception:
        pass
    return 0


def _pdf_outline_to_sections(reader, outline, pages: list[Page]) -> list[Section]:
    """Walk the PDF outline tree and produce Section objects."""
    sections: list[Section] = []
    _walk_outline(reader, outline, pages, sections, level=1)
    return sections


def _walk_outline(reader, items, pages: list[Page], sections: list[Section], level: int) -> None:
    """Recursively walk outline items (may be nested lists)."""
    from pypdf.generic import Destination  # type: ignore[import-untyped]
    chapter_counter: dict[int, int] = {}

    for item in items:
        if isinstance(item, list):
            _walk_outline(reader, item, pages, sections, level + 1)
        else:
            try:
                title = str(item.title).strip()
                page_idx = _pdf_dest_to_page(reader, item)
                # Parse number from title
                m = re.match(
                    r"^(?:chapter|chap|part|unit)\s+(\w+)[:\.\s]",
                    title,
                    re.IGNORECASE,
                )
                if m:
                    number = _parse_chapter_number(m.group(1))
                else:
                    # Try leading "3." or "3.1"
                    m2 = re.match(r"^(\d+)(?:\.\d+)*[\.\s]", title)
                    number = int(m2.group(1)) if m2 else None
                sections.append(Section(
                    level=level,
                    number=number,
                    title=title,
                    start_page=page_idx,
                    text_offset=0,
                ))
            except Exception:
                pass


def _pdf_heuristic_sections(pages: list[Page]) -> list[Section]:
    """Fall back to regex-based heading detection."""
    sections: list[Section] = []
    for page in pages:
        for line in page.text.splitlines():
            result = _detect_heading(line)
            if result:
                lvl, num, title = result
                # Avoid adding a duplicate section at the same page
                if sections and sections[-1].start_page == page.index and sections[-1].title == title:
                    continue
                sections.append(Section(
                    level=lvl,
                    number=num,
                    title=title,
                    start_page=page.index,
                    text_offset=page.text.find(line.strip()),
                ))
    return sections


# ---------------------------------------------------------------------------
# DOCX extraction
# ---------------------------------------------------------------------------

_SYNTHETIC_PAGE_SIZE = 1800  # characters per synthetic page


def _extract_docx(data: bytes) -> ExtractedBook:
    """Extract structure from a DOCX file using python-docx."""
    import io
    from docx import Document  # type: ignore[import-untyped]
    from docx.oxml.ns import qn  # type: ignore[import-untyped]

    doc = Document(io.BytesIO(data))

    sections_out: list[Section] = []
    pages_out: list[Page] = []
    pages_approximate = False

    # Accumulate text into pages; split on explicit page-break paragraphs
    page_buf: list[str] = []
    current_page_chars = 0
    page_index = 0

    def _flush_page() -> None:
        nonlocal page_index, current_page_chars
        text = "\n".join(page_buf)
        pages_out.append(Page(index=page_index, label=str(page_index + 1), text=text[:PAGE_CHAR_CAP]))
        page_buf.clear()
        page_index += 1
        current_page_chars = 0

    has_explicit_breaks = False

    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ""
        text_raw = para.text.strip()

        # Check for explicit page break
        is_page_break = any(
            br.get(qn("w:type")) == "page"
            for run in para.runs
            for br in run._r.findall(qn("w:br"))
        ) if para.runs else False

        if is_page_break:
            has_explicit_breaks = True
            if page_buf:
                _flush_page()
            continue

        # Detect headings
        if style_name.startswith("Heading"):
            # "Heading 1" → level 1, etc.
            parts = style_name.split()
            try:
                level = int(parts[1])
            except (IndexError, ValueError):
                level = 1
            level = min(level, 3)

            # Parse number
            m = re.match(
                r"^(?:(?:chapter|part|unit)\s+)?(\w+)[\.\:\s]",
                text_raw,
                re.IGNORECASE,
            )
            number = _parse_chapter_number(m.group(1)) if m else None

            # Announcement text prefix for TTS
            prefix = {1: "Chapter", 2: "Topic", 3: "Sub-topic"}.get(level, "Section")
            num_str = f" {number}" if number is not None else ""
            announcement = f"{prefix}{num_str}. {text_raw}."

            sections_out.append(Section(
                level=level,
                number=number,
                title=text_raw,
                start_page=page_index,
                text_offset=current_page_chars,
            ))
            page_buf.append(announcement)
            current_page_chars += len(announcement) + 1
        else:
            if text_raw:
                page_buf.append(text_raw)
                current_page_chars += len(text_raw) + 1

        # Synthetic page break at size limit
        if current_page_chars >= _SYNTHETIC_PAGE_SIZE:
            _flush_page()
            pages_approximate = not has_explicit_breaks

    if page_buf:
        _flush_page()
        if not has_explicit_breaks and page_index > 1:
            pages_approximate = True

    if not pages_out:
        pages_out.append(Page(index=0, label="1", text=""))

    return ExtractedBook(
        pages=pages_out,
        sections=sections_out,
        status="ok",
        pages_are_approximate=pages_approximate,
    )


# ---------------------------------------------------------------------------
# TXT / Markdown extraction
# ---------------------------------------------------------------------------

_MD_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_CHAPTER_LINE_RE = re.compile(
    r"^\s*(?:chapter|part|unit|module)\s+(\w+)(?:[:\.\s]+(.+))?$",
    re.IGNORECASE,
)


def _extract_txt(data: bytes) -> ExtractedBook:
    """Extract structure from plain text or Markdown."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")

    lines = text.splitlines()
    sections_out: list[Section] = []
    pages_out: list[Page] = []

    page_buf: list[str] = []
    page_chars = 0
    page_index = 0

    def _flush() -> None:
        nonlocal page_index, page_chars
        pages_out.append(Page(
            index=page_index,
            label=str(page_index + 1),
            text="\n".join(page_buf)[:PAGE_CHAR_CAP],
        ))
        page_buf.clear()
        page_chars = 0
        page_index += 1

    for line in lines:
        stripped = line.strip()

        # Markdown headings
        m_md = _MD_HEADING_RE.match(stripped)
        if m_md:
            level = len(m_md.group(1))
            title = m_md.group(2).strip()
            m_num = re.match(r"^(\w+)[\.\:\s]", title)
            number = _parse_chapter_number(m_num.group(1)) if m_num else None
            sections_out.append(Section(
                level=level, number=number, title=title,
                start_page=page_index, text_offset=page_chars,
            ))
            ann = f"{'Chapter' if level == 1 else 'Section'}. {title}."
            page_buf.append(ann)
            page_chars += len(ann) + 1
        # "Chapter N" headings
        elif _CHAPTER_LINE_RE.match(stripped):
            m_ch = _CHAPTER_LINE_RE.match(stripped)
            assert m_ch
            number = _parse_chapter_number(m_ch.group(1))
            title = (m_ch.group(2) or stripped).strip()
            sections_out.append(Section(
                level=1, number=number, title=title,
                start_page=page_index, text_offset=page_chars,
            ))
            ann = f"Chapter. {title}."
            page_buf.append(ann)
            page_chars += len(ann) + 1
        else:
            if stripped or page_buf:
                page_buf.append(line)
                page_chars += len(line) + 1

        if page_chars >= _SYNTHETIC_PAGE_SIZE:
            _flush()

    if page_buf:
        _flush()

    if not pages_out:
        pages_out.append(Page(index=0, label="1", text=""))

    return ExtractedBook(
        pages=pages_out,
        sections=sections_out,
        status="ok",
        pages_are_approximate=True,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_structure(data: bytes, mime: str) -> ExtractedBook:
    """Parse document bytes into an ``ExtractedBook``.

    Args:
        data: Raw file bytes.
        mime: MIME type string (e.g. ``"application/pdf"``).

    Returns:
        An :class:`ExtractedBook` with pages, sections and status.

    Note:
        Call this inside ``asyncio.to_thread`` from async code — the PDF
        and DOCX parsers are synchronous and potentially slow.
    """
    mime = mime.lower()

    if mime == "application/pdf" or mime.endswith("/pdf"):
        book = _extract_pdf(data)
    elif (
        mime in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        )
        or mime.endswith("docx")
        or mime.endswith("doc")
    ):
        book = _extract_docx(data)
    else:
        # Plain text, Markdown, or anything else
        book = _extract_txt(data)

    # Raise early when the whole document has no usable text (image-only or corrupt)
    total_chars = sum(len(p.text) for p in book.pages)
    if total_chars < 200 and book.status != "needs_ocr":
        raise ExtractionError(
            "No readable text found (image-only or scanned document)"
        )

    return book

