"""Schemas for the accessibility (TTS / STT) endpoints."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel, UpdateModel

# ---------------------------------------------------------------------------
# Shared validators
# ---------------------------------------------------------------------------

_VOICE_RE = re.compile(r"^[A-Za-z0-9_.:+\-]{1,100}$")


def _validate_voice_id(value: str | None) -> str | None:
    if value is None:
        return value
    if not _VOICE_RE.match(value):
        raise ValueError(
            "Voice id must be 1-100 characters of A-Z a-z 0-9 _ . : + -"
        )
    return value


# ---------------------------------------------------------------------------
# TTS request / response
# ---------------------------------------------------------------------------


class TTSRequest(BaseModel):
    """Request body for ``POST /accessibility/tts``."""

    text: str = Field(..., min_length=1, max_length=5_000, description="Text to synthesize.")
    voice: str | None = Field(None, description="Voice id (omit for default).")

    @field_validator("voice")
    @classmethod
    def _check_voice(cls, v: str | None) -> str | None:
        return _validate_voice_id(v)


class VoiceRead(BaseModel):
    """One available TTS voice."""

    id: str
    name: str
    language: str
    provider: str


# ---------------------------------------------------------------------------
# User accessibility settings
# ---------------------------------------------------------------------------

#: Speed type: 0.5–2.0, two decimal places, serialized as float in JSON.
TtsSpeed = Annotated[
    Decimal,
    Field(
        ge=Decimal("0.50"),
        le=Decimal("2.00"),
        decimal_places=2,
        description="Playback speed multiplier (0.50 – 2.00).",
    ),
]


class AccessibilitySettingsRead(ORMModel):
    """Full accessibility settings for the authenticated user."""

    user_id: uuid.UUID
    tts_enabled: bool
    stt_enabled: bool
    high_contrast: bool
    large_text: bool
    tts_voice: str | None
    tts_speed: float  # serialized from Decimal
    created_at: datetime
    updated_at: datetime

    @classmethod
    def defaults(cls, user_id: uuid.UUID) -> "AccessibilitySettingsRead":
        """Return a default (all-false) settings object for a user with no row yet."""
        from datetime import timezone
        now = datetime.now(tz=timezone.utc)
        return cls(
            user_id=user_id,
            tts_enabled=False,
            stt_enabled=False,
            high_contrast=False,
            large_text=False,
            tts_voice=None,
            tts_speed=1.0,
            created_at=now,
            updated_at=now,
        )


class AccessibilitySettingsUpdate(UpdateModel):
    """PATCH body for ``PATCH /users/me/accessibility``.

    All fields are optional; at least one must be supplied (enforced by UpdateModel).
    """

    tts_enabled: bool | None = None
    stt_enabled: bool | None = None
    high_contrast: bool | None = None
    large_text: bool | None = None
    tts_voice: str | None = Field(default=None, description="Voice id or null to clear.")
    tts_speed: TtsSpeed | None = None

    @field_validator("tts_voice")
    @classmethod
    def _check_voice(cls, v: str | None) -> str | None:
        return _validate_voice_id(v)
