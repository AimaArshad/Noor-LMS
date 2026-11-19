"""Accessibility endpoints: TTS synthesis, voice listing.

Access control: any authenticated user can use TTS.
File-scoped TTS (read-aloud) will be added in a later step and will
check ``FileService.can_access`` / classroom membership.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.accessibility import TTSRequest, VoiceRead
from app.services.tts_service import TTSProviderError, get_tts_service

logger = logging.getLogger("educonnect.accessibility")

router = APIRouter()


@router.post(
    "/tts",
    summary="Synthesize text to speech (MP3)",
    response_class=Response,
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio"},
        503: {"description": "No TTS provider available"},
    },
)
async def text_to_speech(
    body: TTSRequest,
    _user: User = Depends(get_current_user),
) -> Response:
    """Return an MP3 audio stream of the given text.

    Synthesis always uses natural speed (1.0).  Playback speed is
    applied client-side by the ``<audio>`` element's ``playbackRate``.
    """
    svc = get_tts_service()
    try:
        mp3_bytes = await svc.synthesize(body.text, voice=body.voice)
    except TTSProviderError as exc:
        logger.error("TTS synthesis failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Text-to-speech is currently unavailable.",
        ) from exc
    return Response(content=mp3_bytes, media_type="audio/mpeg")


@router.get("/voices", summary="List available TTS voices")
async def list_voices(
    _user: User = Depends(get_current_user),
) -> list[VoiceRead]:
    """Return every voice the server can synthesize with."""
    svc = get_tts_service()
    return [
        VoiceRead(id=v.id, name=v.name, language=v.language, provider=v.provider)
        for v in svc.list_voices()
    ]
