from app.services.structure_extraction import Page, _pdf_chapter_opener_sections


def _p(i, text):
    return Page(index=i, label=str(i + 1), text=text)


def test_chapter_openers_with_toc():
    pages = [
        _p(0, "PHYSICS\nCover"),
        _p(1, "CONTENTS\nChapter No. Description Page No.\nThermal Physics 1 1\nWaves 2 5"),
        _p(2, "After studying this chapter, the students will be able to:\ntext"),
        _p(3, "Thermal Physics\n13.1 KINETIC THEORY OF GASES\ntext"),
        _p(4, "Multiple Choice Questions\nWhich is true?\n"),
        _p(5, "After studying this chapter, the students will be able to:\ntext"),
        _p(6, "Waves\ntext"),
    ]
    secs = _pdf_chapter_opener_sections(pages)
    top = [s for s in secs if s.level == 1]
    assert [s.title for s in top] == ["Thermal Physics", "Waves"]
    assert [s.start_page for s in top] == [2, 5]
    assert any(s.level == 2 and "Kinetic" in s.title for s in secs)
    assert not any("?" in s.title for s in secs)


def test_no_openers_returns_empty():
    assert _pdf_chapter_opener_sections([_p(0, "hello world")]) == []