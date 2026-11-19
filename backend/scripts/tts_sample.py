#!/usr/bin/env python3
"""Generate a sample MP3 from a Piper (or espeak) voice.

Usage::

    # Default voice
    python scripts/tts_sample.py "Hello, this is EduConnect."

    # Specific voice
    python scripts/tts_sample.py "Hello from Amy." --voice en_US-amy-medium

    # List available voices
    python scripts/tts_sample.py --list-voices

The output file is written to ``./sample_<voice>.mp3``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running from the backend/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.tts_service import TTSService, build_providers, transcode_to_mp3  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a sample TTS MP3 file.")
    parser.add_argument("text", nargs="?", default="Hello, welcome to EduConnect.")
    parser.add_argument("--voice", "-v", default=None, help="Voice id (file stem of .onnx model)")
    parser.add_argument("--output", "-o", default=None, help="Output file path")
    parser.add_argument("--list-voices", action="store_true", help="List available voices and exit")
    args = parser.parse_args()

    providers = build_providers()
    if not providers:
        print("ERROR: No TTS providers available. Check PIPER_VOICES_DIR or install espeak-ng.")
        sys.exit(1)

    svc = TTSService(providers)

    if args.list_voices:
        voices = svc.list_voices()
        if not voices:
            print("No voices found.")
        for v in voices:
            print(f"  {v.id:30s}  lang={v.language}  provider={v.provider}")
        return

    voice = args.voice
    resolved = providers[0].resolve_voice(voice)
    output = args.output or f"sample_{resolved}.mp3"

    print(f"Synthesizing with voice={resolved} ...")
    mp3_bytes = await svc.synthesize(args.text, voice=voice)
    Path(output).write_bytes(mp3_bytes)
    print(f"Wrote {len(mp3_bytes):,} bytes → {output}")


if __name__ == "__main__":
    asyncio.run(main())

