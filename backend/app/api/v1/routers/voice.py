"""Voice command and transcription endpoints.

POST /voice/command   — parse a text command and resolve DB targets
POST /voice/transcribe — transcribe uploaded audio via faster-whisper
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.db.session import get_db
from app.models import User
from app.schemas.voice import TranscribeResponse, VoiceCommandRequest, VoiceCommandResponse
from app.services.transcription_service import transcribe_audio as _do_transcribe
from app.services.voice_command_service import resolve_voice_command

router = APIRouter()

_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB


def _get_db_dep(db: Annotated[AsyncSession, Depends(get_db)]) -> AsyncSession:
    return db


# ---------------------------------------------------------------------------
# POST /voice/command
# ---------------------------------------------------------------------------


@router.post(
    "/command",
    response_model=VoiceCommandResponse,
    summary="Resolve a voice command to a navigation action",
    responses={401: {}, 404: {}},
)
async def voice_command(
    body: VoiceCommandRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VoiceCommandResponse:
    """Parse *text* (a voice transcript) and resolve it against the caller's
    accessible audiobooks.

    * ``audiobook_id`` pins the target book; omit to let the service pick the
      best match from the caller's library.
    * Response ``speech`` is the sentence to read aloud (screen-reader / TTS).
    * Response ``action`` is the UI action to perform on the client.
    """
    return await resolve_voice_command(
        text=body.text,
        db=db,
        user=user,
        audiobook_id=body.audiobook_id,
    )


# ---------------------------------------------------------------------------
# POST /voice/transcribe
# ---------------------------------------------------------------------------


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    summary="Transcribe audio to text (faster-whisper base.en)",
    responses={401: {}, 413: {}, 503: {}},
)
async def transcribe_audio(
    user: CurrentUser,
    audio: Annotated[UploadFile, File(description="Audio file (WAV, WebM, MP3, OGG — max 10 MB)")],
) -> TranscribeResponse:
    """Accept an audio upload and return the English transcript.

    * Model: ``faster-whisper`` ``base.en``, CPU, int8.
    * Model is lazy-loaded on first call; subsequent calls are fast.
    * Max file size: 10 MB.
    """
    data = await audio.read(_MAX_AUDIO_BYTES + 1)
    if len(data) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "Audio file exceeds the 10 MB limit",
        )
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Audio file is empty")

    try:
        import asyncio

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _do_transcribe, data)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Transcription failed: {exc}",
        ) from exc

    return TranscribeResponse(text=text, language="en")
