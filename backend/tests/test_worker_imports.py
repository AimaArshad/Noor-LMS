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

    # Use at least 200 chars so the minimum-text guard does not raise ExtractionError.
    body = "Chapter 1 Introduction\n" + ("Hello world. " * 20) + "\n"
    book = extract_structure(body.encode(), "text/plain")
    assert book.pages and book.pages[0].index == 0
    assert book.status == "ok"