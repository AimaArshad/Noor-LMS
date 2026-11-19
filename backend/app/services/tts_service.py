"""Text-to-Speech providers: Piper (neural, offline) and espeak (fallback).

Provider chain
--------------
``build_providers()`` returns an ordered list of available providers.
``TTSService`` tries them in order, caches the resulting MP3 on disk,
and returns the bytes.

Design decisions
~~~~~~~~~~~~~~~~
* Speed is ALWAYS 1.0 for synthesis — playback speed is applied client-side.
* Piper voice models are loaded once per process and held in a module-level
  cache behind a lock (safe across async + threaded use).
* The cache key includes the **provider name** so espeak fallback audio is
  never served from a Piper cache slot (and vice versa).
* OCR is NOT in scope yet, but ``text_for_file()`` accepts a pluggable
  ``extract_text`` callable so an OCR adapter can be dropped in later.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import subprocess
import threading
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger("educonnect.tts")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #
class TTSProviderError(Exception):
    """A TTS provider could not synthesise audio.

    Parameters
    ----------
    transient:
        ``True`` when retrying may help (e.g. subprocess timeout).
        ``False`` for permanent errors (missing model file).
    """

    def __init__(self, message: str, *, transient: bool = True) -> None:
        super().__init__(message)
        self.transient = transient


# ------------------------------------------------------------------ #
# Data classes
# ------------------------------------------------------------------ #
@dataclass(frozen=True, slots=True)
class VoiceInfo:
    """Metadata about one available TTS voice."""

    id: str
    name: str
    language: str
    provider: str


# ------------------------------------------------------------------ #
# Abstract base
# ------------------------------------------------------------------ #
class TTSProvider(ABC):
    """Interface every TTS backend implements."""

    name: str

    @abstractmethod
    async def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        """Return raw WAV bytes for ``text``."""

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]:
        """Available voices for this provider."""

    @abstractmethod
    def default_voice(self) -> str:
        """Id of the default voice."""

    def resolve_voice(self, voice_id: str | None) -> str:
        """Map an arbitrary id to one the provider actually knows."""
        if voice_id is None:
            return self.default_voice()
        known = {v.id for v in self.list_voices()}
        return voice_id if voice_id in known else self.default_voice()


# ------------------------------------------------------------------ #
# Piper provider
# ------------------------------------------------------------------ #
_piper_cache: dict[str, object] = {}  # model_path → PiperVoice
_piper_lock = threading.Lock()
# Piper is NOT thread-safe: guard all synthesis calls with this lock.
_piper_synth_lock = threading.Lock()


def _load_piper_voice(model_path: str) -> object:
    """Load (or return cached) PiperVoice object — thread-safe."""
    with _piper_lock:
        if model_path not in _piper_cache:
            from piper.voice import PiperVoice  # type: ignore[import-untyped]

            _piper_cache[model_path] = PiperVoice.load(model_path)
        return _piper_cache[model_path]


class PiperTTSProvider(TTSProvider):
    """Offline neural TTS using Piper (rhasspy/piper).

    Voice models are ``.onnx`` files with a companion ``.onnx.json`` config.
    They are stored in ``PIPER_VOICES_DIR``.
    """

    name = "piper"

    def __init__(self, voices_dir: Path, default_voice: str) -> None:
        self._voices_dir = voices_dir
        self._default_voice = default_voice
        self._voices: list[VoiceInfo] | None = None

    # ---- synthesis ------------------------------------------------- #
    async def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        voice_id = self.resolve_voice(voice)
        model_path = self._voices_dir / f"{voice_id}.onnx"
        if not model_path.is_file():
            raise TTSProviderError(
                f"Piper voice model not found: {model_path}",
                transient=False,
            )
        return await asyncio.to_thread(self._synthesize_sync, str(model_path), text)

    @staticmethod
    def _synthesize_sync(model_path: str, text: str) -> bytes:
        """Run synthesis in a worker thread (blocking I/O + ONNX inference).

        Uses ``synthesize_wav`` if available (piper-tts ≥1.5), otherwise
        falls back to ``synthesize(text, wav_file)`` (older API).
        """
        voice = _load_piper_voice(model_path)
        buf = io.BytesIO()
        with _piper_synth_lock:
            with wave.open(buf, "wb") as wav_file:
                if hasattr(voice, "synthesize_wav"):
                    voice.synthesize_wav(text, wav_file)  # type: ignore[union-attr]
                else:
                    voice.synthesize(text, wav_file)  # type: ignore[union-attr]
        buf.seek(0)
        return buf.read()

    # ---- voice listing --------------------------------------------- #
    def list_voices(self) -> list[VoiceInfo]:
        if self._voices is not None:
            return self._voices
        voices: list[VoiceInfo] = []
        if not self._voices_dir.is_dir():
            self._voices = voices
            return voices
        for onnx in sorted(self._voices_dir.glob("*.onnx")):
            json_path = onnx.with_suffix(".onnx.json")
            lang = "en_US"
            if json_path.is_file():
                try:
                    meta = json.loads(json_path.read_text())
                    lang = meta.get("language", {}).get("code", lang) if isinstance(meta, dict) else lang
                except Exception:  # noqa: BLE001
                    pass
            voice_id = onnx.stem
            voices.append(VoiceInfo(id=voice_id, name=voice_id, language=lang, provider=self.name))
        self._voices = voices
        return voices

    def default_voice(self) -> str:
        return self._default_voice


# ------------------------------------------------------------------ #
# Espeak (local fallback)
# ------------------------------------------------------------------ #
class EspeakTTSProvider(TTSProvider):
    """Fallback TTS using espeak-ng (always available on Linux)."""

    name = "local"

    async def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        voice_name = self.resolve_voice(voice)
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["espeak-ng", "-v", voice_name, "--stdout", "--", text],
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise TTSProviderError(
                    f"espeak-ng failed (rc={result.returncode}): {result.stderr.decode(errors='replace')[:200]}"
                )
            return result.stdout
        except FileNotFoundError:
            raise TTSProviderError("espeak-ng is not installed", transient=False) from None
        except subprocess.TimeoutExpired as exc:
            raise TTSProviderError("espeak-ng timed out") from exc

    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(id="en", name="English (espeak)", language="en", provider=self.name)]

    def default_voice(self) -> str:
        return "en"


# ------------------------------------------------------------------ #
# WAV → MP3 transcoding
# ------------------------------------------------------------------ #
async def transcode_to_mp3(wav_bytes: bytes) -> bytes:
    """Convert WAV bytes to MP3 using ffmpeg (must be on PATH)."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-i", "pipe:0",
        "-f", "mp3",
        "-ab", "128k",
        "-ar", "22050",
        "-ac", "1",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(wav_bytes)
    if proc.returncode != 0:
        raise TTSProviderError(
            f"ffmpeg transcode failed: {stderr.decode(errors='replace')[:200]}"
        )
    return stdout


# ------------------------------------------------------------------ #
# Provider builder
# ------------------------------------------------------------------ #
def build_providers() -> list[TTSProvider]:
    """Build the ordered provider chain based on settings.

    ``TTS_PROVIDER`` values:
    * ``"auto"``  — try piper (if model exists), then espeak.
    * ``"piper"`` — piper only (logs warning if model missing).
    * ``"local"`` — espeak only.
    """
    choice = settings.TTS_PROVIDER
    providers: list[TTSProvider] = []

    if choice in ("auto", "piper"):
        model_file = settings.PIPER_VOICES_DIR / f"{settings.PIPER_DEFAULT_VOICE}.onnx"
        if model_file.is_file():
            providers.append(
                PiperTTSProvider(settings.PIPER_VOICES_DIR, settings.PIPER_DEFAULT_VOICE)
            )
        elif choice == "piper":
            logger.warning(
                "TTS_PROVIDER=piper but model %s not found. "
                "Download it to %s or set TTS_PROVIDER=auto for espeak fallback.",
                model_file,
                settings.PIPER_VOICES_DIR,
            )
        else:
            logger.info(
                "Piper voice model %s not found; espeak will be used as fallback.",
                model_file,
            )

    if choice in ("auto", "local"):
        providers.append(EspeakTTSProvider())

    if not providers:
        logger.warning("No TTS providers configured. TTS endpoints will return 503.")

    return providers


# ------------------------------------------------------------------ #
# TTSService — the high-level API used by routers
# ------------------------------------------------------------------ #
class TTSService:
    """High-level TTS with provider fallback and disk caching."""

    def __init__(self, providers: list[TTSProvider] | None = None) -> None:
        self.providers = providers if providers is not None else build_providers()
        self._cache_dir = settings.TTS_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ---- cache ----------------------------------------------------- #
    @staticmethod
    def _cache_key(text: str, voice: str, provider: str) -> str:
        """Deterministic cache key.

        Includes the **provider name** so that espeak fallback audio is never
        served from a Piper cache slot (and vice versa).
        """
        raw = f"{provider}|{voice}|{text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_path(self, key: str) -> Path:
        # Two-level sharding: first 2 hex chars as subdirectory.
        return self._cache_dir / key[:2] / f"{key}.mp3"

    async def _get_cached(self, key: str) -> bytes | None:
        path = self._cache_path(key)
        if path.is_file():
            return await asyncio.to_thread(path.read_bytes)
        return None

    async def _put_cache(self, key: str, data: bytes) -> None:
        path = self._cache_path(key)
        await asyncio.to_thread(self._write_cache, path, data)

    @staticmethod
    def _write_cache(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    # ---- public API ------------------------------------------------ #
    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
    ) -> bytes:
        """Synthesize ``text`` to MP3 bytes.

        Speed is always 1.0 for synthesis (playback speed is client-side).

        Raises:
            TTSProviderError: when no provider can synthesize.
        """
        if not self.providers:
            raise TTSProviderError("No TTS providers available", transient=False)

        last_error: TTSProviderError | None = None
        for provider in self.providers:
            resolved_voice = provider.resolve_voice(voice)
            cache_key = self._cache_key(text, resolved_voice, provider.name)

            cached = await self._get_cached(cache_key)
            if cached is not None:
                return cached

            try:
                wav_bytes = await provider.synthesize(text, voice=voice)
                mp3_bytes = await transcode_to_mp3(wav_bytes)
                await self._put_cache(cache_key, mp3_bytes)
                return mp3_bytes
            except TTSProviderError as exc:
                logger.warning("TTS provider %s failed: %s", provider.name, exc)
                last_error = exc
                continue

        raise last_error or TTSProviderError("All TTS providers failed", transient=False)

    def list_voices(self) -> list[VoiceInfo]:
        """Aggregate voices from all providers."""
        voices: list[VoiceInfo] = []
        seen: set[str] = set()
        for provider in self.providers:
            for v in provider.list_voices():
                if v.id not in seen:
                    voices.append(v)
                    seen.add(v.id)
        return voices


# ------------------------------------------------------------------ #
# Module-level singleton (lazy)
# ------------------------------------------------------------------ #
_service: TTSService | None = None
_service_lock = threading.Lock()


def get_tts_service() -> TTSService:
    """Return the shared TTSService singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = TTSService()
    return _service
