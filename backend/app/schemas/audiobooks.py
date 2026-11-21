"""Pydantic schemas for the audiobook feature.

Naming conventions:
- ``*Create``  — request bodies for POST
- ``*Update``  — request bodies for PATCH/PUT
- ``*Read``    — response models (ORM-validated)
- ``*ListItem``— lightweight list-view response
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.audiobook_enums import AudiobookStatus, SegmentStatus


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class AudiobookCreate(BaseModel):
    """Body for POST /classrooms/{id}/audiobooks."""

    file_id: uuid.UUID
    title: str | None = Field(None, max_length=512)

    model_config = {"extra": "forbid"}


class PlaybackProgressUpdate(BaseModel):
    """Body for PUT /audiobooks/{id}/progress."""

    segment_seq: int = Field(ge=0)
    offset_ms: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AudiobookRead(BaseModel):
    """Full audiobook row (returned from create/rebuild)."""

    id: uuid.UUID
    classroom_id: uuid.UUID
    file_id: uuid.UUID
    title: str
    status: AudiobookStatus
    page_count: int | None
    pages_approximate: bool
    total_duration_ms: int | None
    voice: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AudiobookListItem(BaseModel):
    """Lightweight item returned from GET /audiobooks."""

    id: uuid.UUID
    title: str
    classroom_name: str
    status: AudiobookStatus
    progress_pct: float | None
    page_count: int | None


class SectionNode(BaseModel):
    """One entry in the audiobook outline tree."""

    id: uuid.UUID
    seq: int
    parent_id: uuid.UUID | None
    level: int
    number: int | None
    title: str
    start_page: int
    end_page: int | None
    first_segment_seq: int | None
    last_segment_seq: int | None


class SegmentInfo(BaseModel):
    """Lightweight segment descriptor (no audio bytes) in the manifest."""

    seq: int
    section_id: uuid.UUID | None
    page_label: str
    duration_ms: int | None
    status: SegmentStatus


class PlaybackProgressRead(BaseModel):
    """Current playback position."""

    segment_seq: int
    offset_ms: int
    updated_at: datetime


class AudiobookManifest(BaseModel):
    """Full player manifest: outline + segments + progress."""

    id: uuid.UUID
    title: str
    status: AudiobookStatus
    page_count: int | None
    total_duration_ms: int | None
    sections: list[SectionNode]
    segments: list[SegmentInfo]
    progress: PlaybackProgressRead | None


class SearchHit(BaseModel):
    """One result from GET /audiobooks/{id}/search."""

    section_id: uuid.UUID | None
    section_title: str | None
    segment_seq: int | None
    page_label: str | None
    snippet: str | None
    rank: float

