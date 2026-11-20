"""Audiobook feature enums."""

from __future__ import annotations

import enum


class AudiobookStatus(enum.StrEnum):
    """Lifecycle of an audiobook."""

    QUEUED = "queued"
    EXTRACTING = "extracting"
    SYNTHESIZING = "synthesizing"
    READY = "ready"
    FAILED = "failed"
    NEEDS_OCR = "needs_ocr"


class SegmentStatus(enum.StrEnum):
    """Synthesis status of a single audio segment."""

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"

