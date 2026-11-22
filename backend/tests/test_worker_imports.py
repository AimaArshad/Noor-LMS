def test_worker_lazy_imports_resolve() -> None:
    from app.services.segmenter import SegmentDraft, build_segments  # noqa: F401
    from app.services.structure_extraction import ExtractionError  # noqa: F401
    from app.services.tts_service import (  # noqa: F401
        TTSProviderError,
        TTSService,
        build_providers,
    )

def test_extract_structure_smoke() -> None:
    from app.services.structure_extraction import extract_structure

    book = extract_structure(b"Chapter 1 Intro\nHello world.\n", "text/plain")
    assert book.pages and book.pages[0].index == 0
    assert book.status == "ok"    