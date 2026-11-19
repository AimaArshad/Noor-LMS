"""Tests for TTS service: Piper provider, fallback order, caching, voice listing.

All tests fake the piper and ffmpeg calls so no model file or binary is needed
in CI.  One test is marked to skip when the model file is absent; it really
synthesizes a sentence and checks the MP3 header bytes.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Env setup (must be before importing app modules)
# ---------------------------------------------------------------------------
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-1234567890")


from app.services.tts_service import (  # noqa: E402
    EspeakTTSProvider,
    PiperTTSProvider,
    TTSProviderError,
    TTSService,
    VoiceInfo,
    build_providers,
    transcode_to_mp3,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_wav_bytes(num_frames: int = 100, sample_rate: int = 22050) -> bytes:
    """Create minimal valid WAV bytes for testing."""
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)
    buf.seek(0)
    return buf.read()


FAKE_WAV = _make_wav_bytes()
# A tiny valid MP3 frame header (sync word 0xFFE0 + padding)
FAKE_MP3 = b"\xff\xe0" + b"\x00" * 200


# ---------------------------------------------------------------------------
# PiperTTSProvider unit tests
# ---------------------------------------------------------------------------
class TestPiperProvider:
    def test_list_voices_empty_dir(self, tmp_path: Path) -> None:
        prov = PiperTTSProvider(tmp_path, "default")
        assert prov.list_voices() == []

    def test_list_voices_discovers_onnx(self, tmp_path: Path) -> None:
        (tmp_path / "en_US-test-medium.onnx").write_bytes(b"fake")
        (tmp_path / "en_US-test-medium.onnx.json").write_text(
            '{"language": {"code": "en_US"}}'
        )
        prov = PiperTTSProvider(tmp_path, "en_US-test-medium")
        voices = prov.list_voices()
        assert len(voices) == 1
        assert voices[0].id == "en_US-test-medium"
        assert voices[0].language == "en_US"
        assert voices[0].provider == "piper"

    def test_list_voices_no_json(self, tmp_path: Path) -> None:
        (tmp_path / "voice.onnx").write_bytes(b"fake")
        prov = PiperTTSProvider(tmp_path, "voice")
        voices = prov.list_voices()
        assert len(voices) == 1
        assert voices[0].language == "en_US"  # fallback

    def test_default_voice(self, tmp_path: Path) -> None:
        prov = PiperTTSProvider(tmp_path, "my-voice")
        assert prov.default_voice() == "my-voice"

    def test_resolve_voice_known(self, tmp_path: Path) -> None:
        (tmp_path / "v1.onnx").write_bytes(b"fake")
        prov = PiperTTSProvider(tmp_path, "v1")
        assert prov.resolve_voice("v1") == "v1"

    def test_resolve_voice_unknown_falls_back(self, tmp_path: Path) -> None:
        (tmp_path / "v1.onnx").write_bytes(b"fake")
        prov = PiperTTSProvider(tmp_path, "v1")
        assert prov.resolve_voice("nonexistent") == "v1"

    @pytest.mark.asyncio
    async def test_synthesize_missing_model_raises(self, tmp_path: Path) -> None:
        prov = PiperTTSProvider(tmp_path, "missing")
        with pytest.raises(TTSProviderError, match="not found"):
            await prov.synthesize("hello")

    @pytest.mark.asyncio
    async def test_synthesize_calls_piper(self, tmp_path: Path) -> None:
        (tmp_path / "v1.onnx").write_bytes(b"fake")
        prov = PiperTTSProvider(tmp_path, "v1")
        with patch.object(prov, "_synthesize_sync", return_value=FAKE_WAV):
            result = await prov.synthesize("hello", voice="v1")
        assert result == FAKE_WAV


# ---------------------------------------------------------------------------
# EspeakTTSProvider unit tests
# ---------------------------------------------------------------------------
class TestEspeakProvider:
    def test_list_voices(self) -> None:
        prov = EspeakTTSProvider()
        voices = prov.list_voices()
        assert len(voices) == 1
        assert voices[0].provider == "local"

    def test_default_voice(self) -> None:
        prov = EspeakTTSProvider()
        assert prov.default_voice() == "en"


# ---------------------------------------------------------------------------
# build_providers() tests
# ---------------------------------------------------------------------------
class TestBuildProviders:
    def test_auto_no_model_gives_espeak(self, tmp_path: Path) -> None:
        with (
            patch("app.services.tts_service.settings") as mock_settings,
        ):
            mock_settings.TTS_PROVIDER = "auto"
            mock_settings.PIPER_VOICES_DIR = tmp_path
            mock_settings.PIPER_DEFAULT_VOICE = "nonexistent"
            mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
            providers = build_providers()
        assert len(providers) == 1
        assert providers[0].name == "local"

    def test_auto_with_model_gives_piper_first(self, tmp_path: Path) -> None:
        (tmp_path / "v1.onnx").write_bytes(b"fake")
        with patch("app.services.tts_service.settings") as mock_settings:
            mock_settings.TTS_PROVIDER = "auto"
            mock_settings.PIPER_VOICES_DIR = tmp_path
            mock_settings.PIPER_DEFAULT_VOICE = "v1"
            mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
            providers = build_providers()
        assert len(providers) == 2
        assert providers[0].name == "piper"
        assert providers[1].name == "local"

    def test_local_only(self, tmp_path: Path) -> None:
        with patch("app.services.tts_service.settings") as mock_settings:
            mock_settings.TTS_PROVIDER = "local"
            mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
            providers = build_providers()
        assert len(providers) == 1
        assert providers[0].name == "local"

    def test_piper_only_missing_warns(self, tmp_path: Path) -> None:
        with patch("app.services.tts_service.settings") as mock_settings:
            mock_settings.TTS_PROVIDER = "piper"
            mock_settings.PIPER_VOICES_DIR = tmp_path
            mock_settings.PIPER_DEFAULT_VOICE = "missing"
            mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
            providers = build_providers()
        assert len(providers) == 0


# ---------------------------------------------------------------------------
# TTSService tests (caching, fallback)
# ---------------------------------------------------------------------------
class TestTTSService:
    @pytest.mark.asyncio
    async def test_synthesize_uses_first_provider(self, tmp_path: Path) -> None:
        prov1 = MagicMock(spec=PiperTTSProvider)
        prov1.name = "piper"
        prov1.resolve_voice.return_value = "v1"
        prov1.synthesize = AsyncMock(return_value=FAKE_WAV)

        with patch("app.services.tts_service.transcode_to_mp3", new_callable=AsyncMock) as mock_transcode:
            mock_transcode.return_value = FAKE_MP3
            with patch("app.services.tts_service.settings") as mock_settings:
                mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
                svc = TTSService(providers=[prov1])
                result = await svc.synthesize("hello")

        assert result == FAKE_MP3
        prov1.synthesize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_hit_on_second_call(self, tmp_path: Path) -> None:
        prov = MagicMock(spec=PiperTTSProvider)
        prov.name = "piper"
        prov.resolve_voice.return_value = "v1"
        prov.synthesize = AsyncMock(return_value=FAKE_WAV)

        with patch("app.services.tts_service.transcode_to_mp3", new_callable=AsyncMock) as mock_transcode:
            mock_transcode.return_value = FAKE_MP3
            with patch("app.services.tts_service.settings") as mock_settings:
                mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
                svc = TTSService(providers=[prov])
                r1 = await svc.synthesize("hello")
                r2 = await svc.synthesize("hello")

        assert r1 == r2 == FAKE_MP3
        # Provider should only be called once; second call is cache hit
        assert prov.synthesize.await_count == 1

    @pytest.mark.asyncio
    async def test_fallback_to_second_provider(self, tmp_path: Path) -> None:
        prov1 = MagicMock(spec=PiperTTSProvider)
        prov1.name = "piper"
        prov1.resolve_voice.return_value = "v1"
        prov1.synthesize = AsyncMock(
            side_effect=TTSProviderError("model missing", transient=False)
        )

        prov2 = MagicMock(spec=EspeakTTSProvider)
        prov2.name = "local"
        prov2.resolve_voice.return_value = "en"
        prov2.synthesize = AsyncMock(return_value=FAKE_WAV)

        with patch("app.services.tts_service.transcode_to_mp3", new_callable=AsyncMock) as mock_transcode:
            mock_transcode.return_value = FAKE_MP3
            with patch("app.services.tts_service.settings") as mock_settings:
                mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
                svc = TTSService(providers=[prov1, prov2])
                result = await svc.synthesize("hello")

        assert result == FAKE_MP3
        prov2.synthesize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_providers_raises(self, tmp_path: Path) -> None:
        with patch("app.services.tts_service.settings") as mock_settings:
            mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
            svc = TTSService(providers=[])
            with pytest.raises(TTSProviderError, match="No TTS providers"):
                await svc.synthesize("hello")

    def test_list_voices_aggregates(self, tmp_path: Path) -> None:
        prov1 = MagicMock(spec=PiperTTSProvider)
        prov1.list_voices.return_value = [
            VoiceInfo(id="v1", name="V1", language="en", provider="piper")
        ]
        prov2 = MagicMock(spec=EspeakTTSProvider)
        prov2.list_voices.return_value = [
            VoiceInfo(id="en", name="English", language="en", provider="local")
        ]
        with patch("app.services.tts_service.settings") as mock_settings:
            mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
            svc = TTSService(providers=[prov1, prov2])
        voices = svc.list_voices()
        assert len(voices) == 2
        assert voices[0].id == "v1"
        assert voices[1].id == "en"

    def test_cache_key_includes_provider(self, tmp_path: Path) -> None:
        """Cache key includes the provider name so piper and espeak never collide."""
        with patch("app.services.tts_service.settings") as mock_settings:
            mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
            svc = TTSService(providers=[])
        k_piper = svc._cache_key("hello", "v1", "piper")
        k_espeak = svc._cache_key("hello", "v1", "local")
        assert k_piper != k_espeak  # same text+voice but different provider → different key

    def test_cache_key_deterministic(self, tmp_path: Path) -> None:
        """Same inputs always produce the same key."""
        with patch("app.services.tts_service.settings") as mock_settings:
            mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
            svc = TTSService(providers=[])
        k1 = svc._cache_key("hello", "v1", "piper")
        k2 = svc._cache_key("hello", "v1", "piper")
        assert k1 == k2

    def test_cache_key_different_text(self, tmp_path: Path) -> None:
        with patch("app.services.tts_service.settings") as mock_settings:
            mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
            svc = TTSService(providers=[])
        k1 = svc._cache_key("hello", "v1", "piper")
        k2 = svc._cache_key("world", "v1", "piper")
        assert k1 != k2

    @pytest.mark.asyncio
    async def test_fallback_caches_under_own_provider_key(self, tmp_path: Path) -> None:
        """When piper fails and espeak succeeds, the cache slot uses 'local', not 'piper'."""
        prov1 = MagicMock(spec=PiperTTSProvider)
        prov1.name = "piper"
        prov1.resolve_voice.return_value = "v1"
        prov1.synthesize = AsyncMock(
            side_effect=TTSProviderError("boom", transient=False)
        )

        prov2 = MagicMock(spec=EspeakTTSProvider)
        prov2.name = "local"
        prov2.resolve_voice.return_value = "en"
        prov2.synthesize = AsyncMock(return_value=FAKE_WAV)

        with patch("app.services.tts_service.transcode_to_mp3", new_callable=AsyncMock) as mock_transcode:
            mock_transcode.return_value = FAKE_MP3
            with patch("app.services.tts_service.settings") as mock_settings:
                mock_settings.TTS_CACHE_DIR = tmp_path / "cache"
                svc = TTSService(providers=[prov1, prov2])
                await svc.synthesize("hello")

        # The cached file should be under the espeak (local) key, not the piper key
        espeak_key = svc._cache_key("hello", "en", "local")
        piper_key = svc._cache_key("hello", "v1", "piper")
        assert svc._cache_path(espeak_key).is_file()
        assert not svc._cache_path(piper_key).is_file()


# ---------------------------------------------------------------------------
# Real synthesis test (skipped when model is absent)
# ---------------------------------------------------------------------------
_DEFAULT_MODEL = Path(
    os.environ.get("PIPER_VOICES_DIR", "./voices")
) / f"{os.environ.get('PIPER_DEFAULT_VOICE', 'en_US-lessac-medium')}.onnx"


@pytest.mark.skipif(
    not _DEFAULT_MODEL.is_file(),
    reason=f"Piper model {_DEFAULT_MODEL} not found — skipping real synthesis test",
)
class TestRealPiperSynthesis:
    """These tests actually run Piper and ffmpeg.  They are slow (~2-5 s)
    and require the model file + ffmpeg on PATH.  CI marks them as skipped."""

    @pytest.mark.asyncio
    async def test_real_synthesis_produces_mp3(self) -> None:
        voices_dir = _DEFAULT_MODEL.parent
        voice_id = _DEFAULT_MODEL.stem
        prov = PiperTTSProvider(voices_dir, voice_id)
        wav = await prov.synthesize("Hello from EduConnect.")
        assert wav[:4] == b"RIFF"  # it's a WAV

        mp3 = await transcode_to_mp3(wav)
        # MP3 starts with either ID3 tag or MPEG sync word
        assert mp3[:3] == b"ID3" or (mp3[0] == 0xFF and (mp3[1] & 0xE0) == 0xE0), (
            f"Output does not look like MP3: first bytes = {mp3[:8].hex()}"
        )
        assert len(mp3) > 100  # sanity: not empty
