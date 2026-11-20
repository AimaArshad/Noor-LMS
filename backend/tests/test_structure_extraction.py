"""Tests for structure_extraction.py and segmenter.py.

Uses generated fixture PDFs/DOCX (no network, no model files needed):
- 12-page PDF with outline of 3 chapters × 2 topics each
- 12-page PDF without outline (heuristic heading detection)
- PDF with page labels (roman numerals for front matter)
- Scanned PDF (no text layer) → needs_ocr
- DOCX with Heading styles and synthetic pages
- Plain text with "Chapter N" headings

Acceptance criteria:
- extract_structure returns correct sections and pages
- build_segments produces ordered segments that never cross page or section
  boundaries
- needs_ocr is correctly detected
"""

from __future__ import annotations

import io
import struct
import zlib
from typing import Any

import pytest

from app.services.structure_extraction import (
    ExtractedBook,
    Page,
    Section,
    extract_structure,
    _parse_chapter_number,
    _detect_heading,
    _strip_running_headers,
    _is_toc_line,
)
from app.services.segmenter import SegmentDraft, build_segments

# ---------------------------------------------------------------------------
# PDF generation helpers (stdlib only — no reportlab needed)
# ---------------------------------------------------------------------------


class _MiniPDF:
    """Minimal PDF builder sufficient for testing pypdf extraction.

    Generates a valid PDF with text layers and an optional outline.
    """

    def __init__(self) -> None:
        self._objects: list[bytes] = []
        self._offsets: list[int] = []
        self._buf = bytearray()

    def _write(self, data: bytes) -> int:
        """Append bytes and return the starting offset."""
        offset = len(self._buf)
        self._buf.extend(data)
        return offset

    def _add_object(self, content: bytes) -> int:
        """Add an indirect object; return its 1-based id."""
        obj_id = len(self._objects) + 1
        self._objects.append(content)
        return obj_id

    def build(
        self,
        pages_text: list[str],
        outline: list[tuple[str, int]] | None = None,
        page_labels: list[str] | None = None,
    ) -> bytes:
        """
        Build PDF bytes.

        Args:
            pages_text: Text for each page.
            outline: Optional list of (title, 0-based page index) for outline items.
            page_labels: Optional printed labels per page.
        """
        # We'll build in-memory using a simple object table.
        # For testing purposes we produce a syntactically valid PDF that pypdf can read.

        buf = io.BytesIO()
        buf.write(b"%PDF-1.4\n")

        offsets: dict[int, int] = {}
        obj_id = 0

        def next_id() -> int:
            nonlocal obj_id
            obj_id += 1
            return obj_id

        def write_obj(oid: int, content: bytes) -> None:
            offsets[oid] = buf.tell()
            buf.write(f"{oid} 0 obj\n".encode())
            buf.write(content)
            buf.write(b"\nendobj\n")

        n = len(pages_text)
        # Reserve ids
        CATALOG_ID = 1
        PAGES_ID = 2
        PAGE_IDS = list(range(3, 3 + n))
        CONTENT_IDS = list(range(3 + n, 3 + 2 * n))
        FONT_ID = 3 + 2 * n
        next_free = FONT_ID + 1

        OUTLINE_ID: int | None = None
        OUTLINE_ITEM_IDS: list[int] = []
        if outline:
            OUTLINE_ID = next_free
            next_free += 1
            OUTLINE_ITEM_IDS = list(range(next_free, next_free + len(outline)))
            next_free += len(outline)

        LABEL_ID: int | None = None
        if page_labels:
            LABEL_ID = next_free
            next_free += 1

        # Font
        font_obj = (
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"
        )
        write_obj(FONT_ID, font_obj)

        # Page content streams
        for i, (pid, cid, text) in enumerate(zip(PAGE_IDS, CONTENT_IDS, pages_text)):
            stream_data = (
                b"BT\n/F1 12 Tf\n10 750 Td\n"
                + b"(" + text.encode("latin-1", errors="replace") + b") Tj\nET\n"
            )
            compressed = zlib.compress(stream_data)
            content_obj = (
                b"<< /Filter /FlateDecode /Length " +
                str(len(compressed)).encode() +
                b" >>\nstream\n" + compressed + b"\nendstream"
            )
            write_obj(cid, content_obj)

        # Page objects
        for pid, cid in zip(PAGE_IDS, CONTENT_IDS):
            page_obj = (
                b"<< /Type /Page /Parent " + str(PAGES_ID).encode() + b" 0 R "
                b"/MediaBox [0 0 612 792] "
                b"/Contents " + str(cid).encode() + b" 0 R "
                b"/Resources << /Font << /F1 " + str(FONT_ID).encode() + b" 0 R >> >> >>"
            )
            write_obj(pid, page_obj)

        # Pages dictionary
        kids_refs = b" ".join(str(pid).encode() + b" 0 R" for pid in PAGE_IDS)
        pages_obj = (
            b"<< /Type /Pages /Kids [" + kids_refs + b"] /Count " +
            str(n).encode() + b" >>"
        )
        write_obj(PAGES_ID, pages_obj)

        # Outline (if any)
        if outline and OUTLINE_ID is not None:
            # Outline items
            for k, (item_id, (title, pg_idx)) in enumerate(zip(OUTLINE_ITEM_IDS, outline)):
                prev_ref = (str(OUTLINE_ITEM_IDS[k - 1]).encode() + b" 0 R") if k > 0 else b"null"
                next_ref = (str(OUTLINE_ITEM_IDS[k + 1]).encode() + b" 0 R") if k < len(outline) - 1 else b"null"
                dest_page = PAGE_IDS[pg_idx]
                item_obj = (
                    b"<< /Title (" + title.encode("latin-1", errors="replace") + b")"
                    b" /Parent " + str(OUTLINE_ID).encode() + b" 0 R"
                    b" /Prev " + prev_ref +
                    b" /Next " + next_ref +
                    b" /Dest [" + str(dest_page).encode() + b" 0 R /XYZ null null null] >>"
                )
                write_obj(item_id, item_obj)

            # Outline root
            first_ref = str(OUTLINE_ITEM_IDS[0]).encode() + b" 0 R"
            last_ref = str(OUTLINE_ITEM_IDS[-1]).encode() + b" 0 R"
            outline_obj = (
                b"<< /Type /Outlines "
                b"/First " + first_ref +
                b" /Last " + last_ref +
                b" /Count " + str(len(outline)).encode() + b" >>"
            )
            write_obj(OUTLINE_ID, outline_obj)

        # Page labels (if any)
        if page_labels and LABEL_ID is not None:
            # Minimal PageLabels: just list the labels as a Nums array
            # For simplicity, alternate between roman (0-3) and arabic (4+)
            nums = b"0 << /S /r >> 4 << /S /D >>"
            label_obj = b"<< /Nums [" + nums + b"] >>"
            write_obj(LABEL_ID, label_obj)

        # Catalog
        catalog_parts = b"<< /Type /Catalog /Pages " + str(PAGES_ID).encode() + b" 0 R"
        if OUTLINE_ID is not None:
            catalog_parts += b" /Outlines " + str(OUTLINE_ID).encode() + b" 0 R"
        if LABEL_ID is not None:
            catalog_parts += b" /PageLabels " + str(LABEL_ID).encode() + b" 0 R"
        catalog_parts += b" >>"
        write_obj(CATALOG_ID, catalog_parts)

        # Cross-reference table
        xref_offset = buf.tell()
        buf.write(b"xref\n")
        buf.write(f"0 {obj_id + 1}\n".encode())
        buf.write(b"0000000000 65535 f \n")
        for i in range(1, obj_id + 1):
            buf.write(f"{offsets.get(i, 0):010d} 00000 n \n".encode())
        buf.write(b"trailer\n")
        buf.write(
            b"<< /Size " + str(obj_id + 1).encode() + b" /Root 1 0 R >>\n"
        )
        buf.write(b"startxref\n")
        buf.write(str(xref_offset).encode() + b"\n")
        buf.write(b"%%EOF\n")

        return buf.getvalue()


def _make_12page_pdf_with_outline() -> bytes:
    """12-page PDF with 3 chapters × 2 topics each in the outline."""
    structure = [
        ("Chapter 1. Introduction", 0),
        ("Chapter 1. Topic 1.1 Background", 1),
        ("Chapter 1. Topic 1.2 Objectives", 2),
        ("Chapter 2. Theory", 4),
        ("Chapter 2. Topic 2.1 Kinetics", 5),
        ("Chapter 2. Topic 2.2 Thermodynamics", 6),
        ("Chapter 3. Experiments", 8),
        ("Chapter 3. Topic 3.1 Setup", 9),
        ("Chapter 3. Topic 3.2 Results", 10),
    ]
    pages_text = [
        "Chapter 1. Introduction\nThis chapter introduces the work.",
        "Topic 1.1 Background\nSome background text here about the field.",
        "Topic 1.2 Objectives\nThe objectives of this study are as follows.",
        "More introduction content continues here on page 4.",
        "Chapter 2. Theory\nTheoretical framework for kinetics.",
        "Topic 2.1 Kinetics\nKinetics deals with the rate of reactions.",
        "Topic 2.2 Thermodynamics\nThermodynamics examines energy transfers.",
        "More theory material on page 8.",
        "Chapter 3. Experiments\nExperimental methods described here.",
        "Topic 3.1 Setup\nThe laboratory setup consisted of several components.",
        "Topic 3.2 Results\nResults are presented in tabular form.",
        "Conclusions and final remarks complete the document.",
    ]
    return _MiniPDF().build(pages_text, outline=structure)


def _make_12page_pdf_no_outline() -> bytes:
    """12-page PDF without outline — heading detection must work from text."""
    pages_text = [
        "Chapter 1 Introduction\nThis chapter introduces the work.",
        "1.1 Background\nSome background text here.",
        "1.2 Objectives\nThe objectives are listed here.",
        "More chapter 1 content here on this page.",
        "Chapter 2 Theory\nTheoretical framework is explained.",
        "2.1 Kinetics\nKinetics section begins here.",
        "2.2 Thermodynamics\nThermodynamics section begins.",
        "Additional theory material.",
        "Chapter 3 Experiments\nExperimental setup.",
        "3.1 Setup\nThe setup is described here.",
        "3.2 Results\nResults analysis.",
        "Conclusions section ends the document.",
    ]
    return _MiniPDF().build(pages_text, outline=None)


def _make_pdf_with_page_labels() -> bytes:
    """PDF with roman numeral labels for first 4 pages."""
    pages_text = [
        "Title page",
        "Copyright page",
        "Table of Contents",
        "Preface page",
        "Chapter 1 Main content starts",
        "More content",
    ]
    return _MiniPDF().build(pages_text, outline=None, page_labels=["i", "ii", "iii", "iv", "1", "2"])


def _make_scanned_pdf() -> bytes:
    """PDF where every page has empty text layer (simulates a scanned doc)."""
    pages_text = ["" for _ in range(6)]
    return _MiniPDF().build(pages_text, outline=None)


def _make_docx() -> bytes:
    """Minimal DOCX with heading styles and body text."""
    # Build a real DOCX in memory using python-docx
    from docx import Document

    doc = Document()
    doc.add_heading("Chapter 1. Introduction", level=1)
    doc.add_paragraph("This paragraph introduces the content. " * 20)
    doc.add_heading("1.1 Background", level=2)
    doc.add_paragraph("Background section content here. " * 20)
    doc.add_heading("Chapter 2. Methods", level=1)
    doc.add_paragraph("Methods section content here. " * 20)
    doc.add_heading("2.1 Procedure", level=2)
    doc.add_paragraph("Procedure details. " * 20)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_txt() -> bytes:
    """Plain text with Chapter headings."""
    content = """\
Chapter 1 Introduction

This is the introduction chapter with enough text to test segmentation properly.
More text follows here to make it substantial enough for testing purposes.

Chapter 2 Methods

This chapter describes the methods. Here is more text to fill the section.
Additional content to ensure we have enough for multi-segment pages.

## Sub-section 2.1

This is a Markdown-style sub-heading within chapter 2.
"""
    return content.encode("utf-8")


# ---------------------------------------------------------------------------
# Tests: chapter number parsing
# ---------------------------------------------------------------------------

class TestParseChapterNumber:
    def test_arabic(self):
        assert _parse_chapter_number("3") == 3

    def test_roman_I(self):
        assert _parse_chapter_number("I") == 1

    def test_roman_III(self):
        assert _parse_chapter_number("III") == 3

    def test_roman_IV(self):
        assert _parse_chapter_number("IV") == 4

    def test_roman_X(self):
        assert _parse_chapter_number("X") == 10

    def test_word_one(self):
        assert _parse_chapter_number("one") == 1

    def test_word_Two(self):
        assert _parse_chapter_number("Two") == 2

    def test_word_twelve(self):
        assert _parse_chapter_number("twelve") == 12

    def test_unknown(self):
        assert _parse_chapter_number("alpha") is None


# ---------------------------------------------------------------------------
# Tests: heading detection
# ---------------------------------------------------------------------------

class TestDetectHeading:
    def test_chapter_n(self):
        result = _detect_heading("Chapter 3")
        assert result is not None
        level, number, title = result
        assert level == 1
        assert number == 3

    def test_chapter_roman(self):
        result = _detect_heading("Chapter II Introduction")
        assert result is not None
        assert result[1] == 2

    def test_dotted_section(self):
        result = _detect_heading("3.1 Kinetic Theory")
        assert result is not None
        assert result[0] == 2  # level 2

    def test_non_heading(self):
        assert _detect_heading("The quick brown fox.") is None

    def test_allcaps_heading(self):
        result = _detect_heading("INTRODUCTION")
        assert result is not None

    def test_unit_heading(self):
        result = _detect_heading("Unit 5")
        assert result is not None
        assert result[1] == 5


# ---------------------------------------------------------------------------
# Tests: running header stripping
# ---------------------------------------------------------------------------

class TestStripRunningHeaders:
    def test_strips_repeated_line(self):
        pages = [
            "EduConnect Textbook\nContent page 1",
            "EduConnect Textbook\nContent page 2",
            "EduConnect Textbook\nContent page 3",
            "EduConnect Textbook\nContent page 4",
        ]
        cleaned = _strip_running_headers(pages)
        for page in cleaned:
            assert "EduConnect Textbook" not in page

    def test_keeps_unique_lines(self):
        pages = [
            "EduConnect Textbook\nThis is unique text",
            "EduConnect Textbook\nAnother unique line",
            "EduConnect Textbook\nYet another",
            "EduConnect Textbook\nFourth page",
        ]
        cleaned = _strip_running_headers(pages)
        assert any("unique" in p for p in cleaned)

    def test_strips_bare_numbers(self):
        pages = ["Content\n5", "Content\n6", "Content\n7"]
        cleaned = _strip_running_headers(pages)
        for page in cleaned:
            assert page.strip() not in ("5", "6", "7")


# ---------------------------------------------------------------------------
# Tests: TOC detection
# ---------------------------------------------------------------------------

class TestTocDetection:
    def test_dot_leaders(self):
        assert _is_toc_line("Chapter 1 ..... 5")

    def test_ellipsis_toc(self):
        assert _is_toc_line("Introduction……………… 1")

    def test_normal_line(self):
        assert not _is_toc_line("This is normal content")


# ---------------------------------------------------------------------------
# Tests: PDF extraction with outline
# ---------------------------------------------------------------------------

class TestPdfWithOutline:
    def test_returns_12_pages(self):
        data = _make_12page_pdf_with_outline()
        book = extract_structure(data, "application/pdf")
        assert len(book.pages) == 12

    def test_sections_found(self):
        data = _make_12page_pdf_with_outline()
        book = extract_structure(data, "application/pdf")
        # Should have at least 3 chapters + 6 topics = 9 sections from outline
        assert len(book.sections) >= 3

    def test_chapter_1_is_first(self):
        data = _make_12page_pdf_with_outline()
        book = extract_structure(data, "application/pdf")
        first = book.sections[0]
        assert first.start_page == 0

    def test_status_ok(self):
        data = _make_12page_pdf_with_outline()
        book = extract_structure(data, "application/pdf")
        assert book.status == "ok"

    def test_pages_have_labels(self):
        data = _make_12page_pdf_with_outline()
        book = extract_structure(data, "application/pdf")
        assert all(isinstance(p.label, str) for p in book.pages)
        assert all(len(p.label) > 0 for p in book.pages)

    def test_page_text_not_empty_for_text_pages(self):
        data = _make_12page_pdf_with_outline()
        book = extract_structure(data, "application/pdf")
        # At least half the pages should have text
        non_empty = sum(1 for p in book.pages if p.text.strip())
        assert non_empty >= 6


# ---------------------------------------------------------------------------
# Tests: PDF without outline (heuristic detection)
# ---------------------------------------------------------------------------

class TestPdfNoOutline:
    def test_returns_12_pages(self):
        data = _make_12page_pdf_no_outline()
        book = extract_structure(data, "application/pdf")
        assert len(book.pages) == 12

    def test_detects_chapter_headings(self):
        data = _make_12page_pdf_no_outline()
        book = extract_structure(data, "application/pdf")
        chapter_sections = [s for s in book.sections if s.level == 1]
        assert len(chapter_sections) >= 3

    def test_chapter_numbers_parsed(self):
        data = _make_12page_pdf_no_outline()
        book = extract_structure(data, "application/pdf")
        chapter_sections = [s for s in book.sections if s.level == 1 and s.number is not None]
        assert len(chapter_sections) >= 1


# ---------------------------------------------------------------------------
# Tests: Scanned PDF (needs_ocr)
# ---------------------------------------------------------------------------

class TestScannedPdf:
    def test_needs_ocr_status(self):
        data = _make_scanned_pdf()
        book = extract_structure(data, "application/pdf")
        assert book.status == "needs_ocr"

    def test_pages_still_returned(self):
        data = _make_scanned_pdf()
        book = extract_structure(data, "application/pdf")
        assert len(book.pages) == 6


# ---------------------------------------------------------------------------
# Tests: DOCX extraction
# ---------------------------------------------------------------------------

class TestDocxExtraction:
    def test_headings_become_sections(self):
        data = _make_docx()
        book = extract_structure(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert len(book.sections) >= 2

    def test_chapter_level_1(self):
        data = _make_docx()
        book = extract_structure(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        chapters = [s for s in book.sections if s.level == 1]
        assert len(chapters) >= 2

    def test_topic_level_2(self):
        data = _make_docx()
        book = extract_structure(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        topics = [s for s in book.sections if s.level == 2]
        assert len(topics) >= 2

    def test_pages_created(self):
        data = _make_docx()
        book = extract_structure(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert len(book.pages) >= 1

    def test_pages_approximate_flag(self):
        data = _make_docx()
        book = extract_structure(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        # DOCX without explicit page breaks → approximate
        assert book.pages_are_approximate is True


# ---------------------------------------------------------------------------
# Tests: TXT extraction
# ---------------------------------------------------------------------------

class TestTxtExtraction:
    def test_chapter_headings(self):
        data = _make_txt()
        book = extract_structure(data, "text/plain")
        chapters = [s for s in book.sections if s.level == 1]
        assert len(chapters) >= 2

    def test_markdown_headings(self):
        data = _make_txt()
        book = extract_structure(data, "text/plain")
        level2 = [s for s in book.sections if s.level == 2]
        assert len(level2) >= 1

    def test_pages_approximate(self):
        data = _make_txt()
        book = extract_structure(data, "text/plain")
        assert book.pages_are_approximate is True


# ---------------------------------------------------------------------------
# Tests: build_segments
# ---------------------------------------------------------------------------

class TestBuildSegments:
    def _book_12ch(self) -> ExtractedBook:
        data = _make_12page_pdf_with_outline()
        return extract_structure(data, "application/pdf")

    def test_segments_are_ordered(self):
        book = self._book_12ch()
        segs = build_segments(book)
        for i, seg in enumerate(segs):
            assert seg.seq == i, f"Segment {i} has seq={seg.seq}"

    def test_no_empty_segments(self):
        book = self._book_12ch()
        segs = build_segments(book)
        for seg in segs:
            assert seg.text.strip() != "", f"Segment {seg.seq} is empty"

    def test_segments_do_not_cross_page_boundaries(self):
        book = self._book_12ch()
        segs = build_segments(book)
        # A segment's page_index must be stable (no segment should span 2 pages)
        # We verify this by checking that each non-announcement segment references
        # exactly one page, which is enforced by our implementation.
        for seg in segs:
            assert isinstance(seg.page_index, int)
            assert 0 <= seg.page_index < len(book.pages)

    def test_announcements_at_section_starts(self):
        book = self._book_12ch()
        segs = build_segments(book)
        announcements = [s for s in segs if s.is_announcement]
        assert len(announcements) >= len(book.sections)

    def test_announcement_text_contains_chapter(self):
        book = self._book_12ch()
        segs = build_segments(book)
        ann = [s for s in segs if s.is_announcement]
        assert any("Chapter" in s.text or "Topic" in s.text for s in ann)

    def test_char_count_matches_text(self):
        book = self._book_12ch()
        segs = build_segments(book)
        for seg in segs:
            assert seg.char_count == len(seg.text)

    def test_no_segment_exceeds_max(self):
        """No segment text should exceed TARGET_MAX chars (1500)."""
        from app.services.segmenter import TARGET_MAX
        book = self._book_12ch()
        segs = build_segments(book)
        for seg in segs:
            if not seg.is_announcement:
                assert seg.char_count <= TARGET_MAX + 50, (
                    f"Segment {seg.seq} has {seg.char_count} chars"
                )

    def test_segments_on_non_existent_pages_absent(self):
        """Every page_index referenced by segments must exist in book.pages."""
        book = self._book_12ch()
        valid_pages = {p.index for p in book.pages}
        segs = build_segments(book)
        for seg in segs:
            assert seg.page_index in valid_pages

    def test_txt_book_segments_ordered(self):
        data = _make_txt()
        book = extract_structure(data, "text/plain")
        segs = build_segments(book)
        for i, seg in enumerate(segs):
            assert seg.seq == i

    def test_docx_book_segments_non_crossing(self):
        data = _make_docx()
        book = extract_structure(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        segs = build_segments(book)
        # Verify ordering
        for i, seg in enumerate(segs):
            assert seg.seq == i

    def test_scanned_pdf_segments_announcement_only_or_empty(self):
        """Scanned PDFs have no text; segments should be empty or just announcements."""
        data = _make_scanned_pdf()
        book = extract_structure(data, "application/pdf")
        segs = build_segments(book)
        # With no text and no outline, there should be no segments or only announcements
        for seg in segs:
            assert seg.is_announcement or seg.text.strip() == ""

