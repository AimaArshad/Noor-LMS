"""Pydantic schemas for voice command and transcription endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class VoiceCommandRequest(BaseModel):
    """Body for POST /voice/command."""

    text: str = Field(min_length=1, max_length=2000)
    audiobook_id: uuid.UUID | None = None

    model_config = {"extra": "forbid"}


class VoiceTarget(BaseModel):
    """Resolved navigation target."""

    audiobook_id: uuid.UUID | None = None
    section_seq: int | None = None
    segment_seq: int | None = None
    page: int | None = None


class VoiceCommandResponse(BaseModel):
    """Response from POST /voice/command."""

    intent: str
    action: str
    target: VoiceTarget
    speech: str


class TranscribeResponse(BaseModel):
    """Response from POST /voice/transcribe."""

    text: str
    language: str = "en"

