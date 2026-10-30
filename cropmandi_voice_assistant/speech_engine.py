"""Speech helpers for CropMandi voice assistant.

Input transcription is performed locally with faster-whisper after its model has
been downloaded once. Speech output uses Microsoft Edge's neural TTS service via
edge-tts; the browser has a local speech-synthesis fallback when that service is
unreachable.
"""
from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from typing import Any

MODEL_NAME = os.getenv("CROPMANDI_WHISPER_MODEL", "base").strip() or "base"
LANGUAGE_CODES = {
    "en": "en", "en-in": "en", "en-us": "en",
    "hi": "hi", "hi-in": "hi",
    "kn": "kn", "kn-in": "kn",
}
TTS_VOICES = {
    "en": "en-IN-NeerjaNeural",
    "hi": "hi-IN-SwaraNeural",
    "kn": "kn-IN-SapnaNeural",
}

_model: Any = None
_model_lock = threading.Lock()


class SpeechEngineUnavailable(RuntimeError):
    """Raised when a speech dependency or speech model is unavailable."""


def language_code(language: str | None) -> str:
    normalized = str(language or "en-IN").strip().lower()
    return LANGUAGE_CODES.get(normalized, LANGUAGE_CODES.get(normalized.split("-")[0], "en"))


def _get_whisper_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SpeechEngineUnavailable(
                "Local speech recognition is not installed. Run: python -m pip install faster-whisper"
            ) from exc
        try:
            # CPU int8 is a practical default for Windows laptops and does not need CUDA.
            _model = WhisperModel(
                MODEL_NAME,
                device="cpu",
                compute_type="int8",
                cpu_threads=max(1, min(6, os.cpu_count() or 2)),
            )
        except Exception as exc:
            raise SpeechEngineUnavailable(
                f"The local speech model '{MODEL_NAME}' could not be loaded. Its first use needs internet to download the model; once cached, transcription runs locally. Check the connection and restart the API."
            ) from exc
    return _model


def _audio_suffix(filename: str | None, content_type: str | None) -> str:
    # Prefer a known audio extension; never trust a path supplied by the browser.
    ext = Path(str(filename or "")).suffix.lower()
    if ext in {".webm", ".ogg", ".wav", ".mp3", ".mp4", ".m4a", ".mpeg", ".mpga", ".flac"}:
        return ext
    mime = str(content_type or "").lower()
    if "ogg" in mime:
        return ".ogg"
    if "mp4" in mime or "m4a" in mime:
        return ".mp4"
    if "wav" in mime:
        return ".wav"
    if "mpeg" in mime or "mp3" in mime:
        return ".mp3"
    return ".webm"


def transcribe_audio_bytes(
    audio_bytes: bytes,
    language: str = "en-IN",
    filename: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    """Transcribe a browser-recorded audio clip with the selected language."""
    if not audio_bytes:
        raise ValueError("The recording was empty. Please record your question again.")

    model = _get_whisper_model()
    language_id = language_code(language)
    suffix = _audio_suffix(filename, content_type)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="cropmandi-voice-", suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        segments, info = model.transcribe(
            tmp_path,
            language=language_id,
            task="transcribe",
            beam_size=3,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return {
            "text": text,
            "language": language_id,
            "detected_language": getattr(info, "language", language_id),
            "language_probability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 3),
            "engine": "faster-whisper-local",
            "model": MODEL_NAME,
        }
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


async def synthesize_audio_bytes(text: str, language: str = "en-IN") -> bytes:
    """Generate natural Indian-language speech using Edge neural TTS voices."""
    try:
        import edge_tts
    except ImportError as exc:
        raise SpeechEngineUnavailable(
            "Multilingual speech output is not installed. Run: python -m pip install edge-tts"
        ) from exc

    language_id = language_code(language)
    voice = TTS_VOICES.get(language_id, TTS_VOICES["en"])
    audio_chunks: list[bytes] = []
    try:
        communicator = edge_tts.Communicate(text=text, voice=voice, rate="+0%", pitch="+0Hz")
        async for chunk in communicator.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                audio_chunks.append(chunk["data"])
    except Exception as exc:
        raise SpeechEngineUnavailable(
            "The neural speech service is unavailable right now. Check internet access; the browser's installed voice will be used as a fallback."
        ) from exc

    audio = b"".join(audio_chunks)
    if not audio:
        raise SpeechEngineUnavailable("The speech service returned no audio. Use the browser voice fallback.")
    return audio
