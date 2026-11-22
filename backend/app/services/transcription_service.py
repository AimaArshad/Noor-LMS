"""Lazy-loaded faster-whisper transcription wrapper.

The model is loaded once per process (singleton) the first time
``transcribe_audio`` is called, so startup is instant.

Settings
--------
``WHISPER_MODEL`` (default ``"base.en"``) is read from config.
The model runs on CPU with int8 quantisation (free, no GPU required).
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger("educonnect.transcription")

_model = None
_model_lock = threading.Lock()


def _get_model():
    """Return the WhisperModel singleton, loading it on first call."""
    global _model  # noqa: PLW0603
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        from faster_whisper import WhisperModel

        from app.core.config import settings

        model_name = getattr(settings, "WHISPER_MODEL", "base.en")
        cache_dir = str(getattr(settings, "WHISPER_CACHE_DIR", None) or "")
        kwargs: dict = {
            "device": "cpu",
            "compute_type": "int8",
        }
        if cache_dir:
            kwargs["download_root"] = cache_dir

        logger.info("Loading Whisper model %r (CPU int8) …", model_name)
        _model = WhisperModel(model_name, **kwargs)
        logger.info("Whisper model %r loaded.", model_name)
        return _model


def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe raw audio bytes and return the English transcript.

    Writes the bytes to a temporary file (faster-whisper needs a path),
    runs inference, and joins all segments with spaces.

    Args:
        audio_bytes: Raw audio bytes in any format ffmpeg can read
                     (WAV, WebM, MP3, OGG …).

    Returns:
        Transcribed text, stripped of leading/trailing whitespace.
    """
    import tempfile
    import os

    model = _get_model()

    # Write to a temp file — faster-whisper needs a seekable file path
    suffix = ".wav"  # most likely upload format; ffmpeg handles others too
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments, _info = model.transcribe(
            tmp_path,
            language="en",
            beam_size=5,
            best_of=5,
            vad_filter=True,
        )
        return " ".join(seg.text for seg in segments).strip()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

