"""Run a real speech-to-text smoke test against an audio file.

Example:
    python -m cropmandi_voice_assistant.smoke_test sample.wav --language en-IN
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .speech_engine import SpeechEngineUnavailable, transcribe_audio_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe a real audio file with CropMandi's configured local speech model.")
    parser.add_argument("audio_file", type=Path, help="A short WAV, MP3, M4A, OGG or WebM recording")
    parser.add_argument("--language", default="en-IN", choices=("en-IN", "hi-IN", "kn-IN"))
    args = parser.parse_args()

    if not args.audio_file.is_file():
        print(f"Audio file not found: {args.audio_file}", file=sys.stderr)
        return 2
    audio = args.audio_file.read_bytes()
    try:
        result = transcribe_audio_bytes(audio, args.language, args.audio_file.name)
    except (SpeechEngineUnavailable, ValueError) as exc:
        print(f"Transcription failed: {exc}", file=sys.stderr)
        return 1

    print("Real audio transcription succeeded.")
    print(f"Engine: {result['engine']} ({result['model']})")
    print(f"Requested language: {result['language']}")
    print(f"Detected language: {result['detected_language']} (probability {result['language_probability']})")
    print(f"Transcript: {result['text']}")
    return 0 if result["text"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
