# """Accessibility endpoints: TTS synthesis, voice listing.

# Access control: any authenticated user can use TTS.
# File-scoped TTS (read-aloud) will be added in a later step and will
# check ``FileService.can_access`` / classroom membership.
# """

# from __future__ import annotations

# import logging

# # from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
# from fastapi import APIRouter,  Depends, HTTPException, Query, Request, status
# from fastapi.responses import Response

# from app.core.deps import get_current_user
# from app.core.config import settings
# from app.core.rate_limit import limiter
# from app.models.user import User
# from app.schemas.accessibility import TTSRequest, VoiceRead
# from app.services.tts_service import TTSProviderError, get_tts_service
# from app.utils.sanitize import clean_multiline

# logger = logging.getLogger("educonnect.accessibility")

# router = APIRouter()


# @router.post(
#     "/tts",
#     summary="Synthesize text to speech (MP3)",
#     response_class=Response,
#     responses={
#         200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio"},
#         422: {"description": "Empty or invalid text / voice"},
#         503: {"description": "No TTS provider available"},
#     },
# )
# @limiter.limit(settings.TTS_RATE_LIMIT)
# async def text_to_speech(
#     request: Request,
#     # body: TTSRequest = Body(...),  # <--- THIS IS THE FIX
#        body: TTSRequest, 
   
#     _user: User = Depends(get_current_user),
# ) -> Response:
#     """Return an MP3 audio stream of the given text.

#     Synthesis always uses natural speed (1.0).  Playback speed is
#     applied client-side by the ``<audio>`` element's ``playbackRate``.

#     Text is sanitised (control characters stripped) before synthesis.
#     An empty string after sanitisation is rejected with 422.
#     """
#     # Sanitise control characters using the project's existing sanitiser.
#     cleaned = clean_multiline(body.text).strip()
#     if not cleaned:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail="text must not be empty after sanitisation",
#         )

#     svc = get_tts_service()
#     try:
#         mp3_bytes = await svc.synthesize(cleaned, voice=body.voice)
#     except TTSProviderError as exc:
#         logger.error("TTS synthesis failed: %s", exc)
#         raise HTTPException(
#             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
#             detail="Text-to-speech is currently unavailable.",
#         ) from exc
#     return Response(content=mp3_bytes, media_type="audio/mpeg")


# @router.get("/voices", summary="List available TTS voices")
# async def list_voices(
#     language: str | None = Query(
#         None,
#         description="Filter by language code prefix (e.g. 'en', 'en_US').",
#     ),
#     _user: User = Depends(get_current_user),
# ) -> list[VoiceRead]:
#     """Return every voice the server can synthesize with.

#     Pass ``?language=en`` to filter to English voices (prefix match).
#     """
#     svc = get_tts_service()
#     voices = [
#         VoiceRead(id=v.id, name=v.name, language=v.language, provider=v.provider)
#         for v in svc.list_voices()
#     ]
#     if language is not None:
#         prefix = language.lower()
#         voices = [v for v in voices if v.language.lower().startswith(prefix)]
#     return voices





"""Accessibility endpoints: TTS synthesis, voice listing.

Access control: any authenticated user can use TTS.
File-scoped TTS (read-aloud) will be added in a later step and will
check ``FileService.can_access`` / classroom membership.
"""

# from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from app.core.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.accessibility import TTSRequest, VoiceRead
from app.services.tts_service import TTSProviderError, get_tts_service
from app.utils.sanitize import clean_multiline

logger = logging.getLogger("educonnect.accessibility")

router = APIRouter()


@router.post(
    "/tts",
    summary="Synthesize text to speech (MP3)",
    response_class=Response,
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio"},
        422: {"description": "Empty or invalid text / voice"},
        503: {"description": "No TTS provider available"},
    },
)
@limiter.limit(settings.TTS_RATE_LIMIT)
async def text_to_speech(
    request: Request,
    body: TTSRequest = Body(...),  # <--- MAKE SURE THIS IS UNCOMMENTED
    _user: User = Depends(get_current_user),
) -> Response:
    """Return an MP3 audio stream of the given text."""
    # Sanitise control characters using the project's existing sanitiser.
    cleaned = clean_multiline(body.text).strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="text must not be empty after sanitisation",
        )

    svc = get_tts_service()
    try:
        mp3_bytes = await svc.synthesize(cleaned, voice=body.voice)
    except TTSProviderError as exc:
        logger.error("TTS synthesis failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Text-to-speech is currently unavailable.",
        ) from exc
    return Response(content=mp3_bytes, media_type="audio/mpeg")


@router.get("/voices", summary="List available TTS voices")
async def list_voices(
    language: str | None = Query(
        None,
        description="Filter by language code prefix (e.g. 'en', 'en_US').",
    ),
    _user: User = Depends(get_current_user),
) -> list[VoiceRead]:
    """Return every voice the server can synthesize with."""
    svc = get_tts_service()
    voices = [
        VoiceRead(id=v.id, name=v.name, language=v.language, provider=v.provider)
        for v in svc.list_voices()
    ]
    if language is not None:
        prefix = language.lower()
        voices = [v for v in voices if v.language.lower().startswith(prefix)]
    return voices