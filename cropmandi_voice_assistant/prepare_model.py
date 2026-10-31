"""Download and verify the configured Faster-Whisper model before a demo.

Run from the project root with:
    python -m cropmandi_voice_assistant.prepare_model
"""
from __future__ import annotations

import sys

from .speech_engine import MODEL_NAME, SpeechEngineUnavailable, _get_whisper_model, get_speech_engine_status


def main() -> int:
    print(f"Preparing CropMandi speech model: {MODEL_NAME}")
    print("The first download requires internet. The model is stored in the local Hugging Face cache.")
    try:
        _get_whisper_model()
    except SpeechEngineUnavailable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    status = get_speech_engine_status()
    print("Speech model downloaded and loaded successfully.")
    print(f"Model: {status['model']}")
    print(f"Cached: {status['model_cached']}")
    print("You can now start the API. The cached model can be used without downloading it again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
