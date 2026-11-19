"""Schemas for the accessibility (TTS / STT) endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """Request body for ``POST /accessibility/tts``."""

    text: str = Field(..., min_length=1, max_length=10_000, description="Text to synthesize.")
    voice: str | None = Field(None, description="Voice id (omit for default).")


class VoiceRead(BaseModel):
    """One available TTS voice."""

    id: str
    name: str
    language: str
    provider: str
