"""Speech helpers for CropMandi voice assistant.

Input transcription is performed locally with faster-whisper after its model has
been downloaded once. Speech output uses Microsoft Edge's neural TTS service via
edge-tts; the browser has a local speech-synthesis fallback when that service is
unreachable.
"""
from __future__ import annotations

import os
import re
from datetime import date
import tempfile
import threading
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
_FILE_ENV = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
MODEL_NAME = str(os.getenv("CROPMANDI_WHISPER_MODEL") or _FILE_ENV.get("CROPMANDI_WHISPER_MODEL") or "large-v3-turbo").strip()
MODEL_DIR = str(os.getenv("CROPMANDI_VOICE_MODEL_DIR") or Path(__file__).resolve().parent / ".models")
PROMPTS = {
    "en": "CropMandi, coffee, Arabica Parchment, Robusta Cherry, black pepper, tomato, potato, paddy, maize, Chikkamagaluru, Hassan, Kolar. Mandi Price AI, HarvestRoute, My Crops, dashboard, Analytics, settings.",
    "hi": "कॉफी, काली मिर्च, धान, टमाटर, आलू, मक्का, हासन, कोलार, अरबिका पार्चमेंट। मंडी प्राइस एआई, हार्वेस्ट रूट, मेरी फसलें, डैशबोर्ड।",
    "kn": "ಕಾಫಿ, ಮೆಣಸು, ಭತ್ತ, ಟೊಮೇಟೊ, ಆಲೂಗಡ್ಡೆ, ಮೆಕ್ಕೆಜೋಳ, ಹಾಸನ, ಕೋಲಾರ, ಚಿಕ್ಕಮಗಳೂರು, ಅರೇಬಿಕಾ ಪಾರ್ಚ್ಮೆಂಟ್. ಮಂಡಿ ಪ್ರೈಸ್ ಎಐ, ಹಾರ್ವೆಸ್ಟ್ ರೂಟ್, ನನ್ನ ಬೆಳೆಗಳು, ಡ್ಯಾಶ್‌ಬೋರ್ಡ್.",
}
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
_transcription_slot = threading.BoundedSemaphore(1)


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
                download_root=MODEL_DIR,
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

    language_id = None if language == "auto" else language_code(language)
    if not _transcription_slot.acquire(blocking=False):
        raise SpeechEngineUnavailable("Speech recognition is busy. Please retry in a moment.")
    suffix = _audio_suffix(filename, content_type)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="cropmandi-voice-", suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        import av
        seconds = 0.0
        with av.open(tmp_path) as container:
            for frame in container.decode(audio=0):
                seconds += frame.samples / frame.sample_rate
                if seconds > 35:
                    raise ValueError("Recording is too long. Please keep it under 30 seconds.")
        if not seconds:
            raise ValueError("No audio samples were found in this recording.")
        model = _get_whisper_model()
        segments, info = model.transcribe(
            tmp_path,
            language=language_id,
            task="transcribe",
            beam_size=5,
            initial_prompt=PROMPTS.get(language_id),
            temperature=0.0,
            repetition_penalty=1.1,
            no_repeat_ngram_size=3,
            max_new_tokens=128,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        segments = list(segments)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        wrong_script = (language_id == "kn" and any("\u0900" <= c <= "\u097f" for c in text)) or (language_id == "hi" and any("\u0c80" <= c <= "\u0cff" for c in text))
        detected = getattr(info, "language", language_id) or "en"
        uncertain = wrong_script or any(getattr(s, "avg_logprob", 0) < -0.8 or getattr(s, "compression_ratio", 0) > 2.4 or len(getattr(s, "tokens", [])) >= 120 for s in segments)
        if language_id is None and (detected not in ("en", "hi", "kn") or float(getattr(info, "language_probability", 0)) < 0.5):
            uncertain = True
        recovery = None
        # Retry only Kannada calendar questions. Never bypass low acoustic
        # quality, truncation, conflicting slots, or automatic-language doubt.
        acoustic_uncertain = any(getattr(s, "avg_logprob", 0) < -0.8 or getattr(s, "compression_ratio", 0) > 2.4 or len(getattr(s, "tokens", [])) >= 120 for s in segments)
        if (language_id == "kn" or (language_id is None and detected == "kn" and not uncertain)) and not acoustic_uncertain:
            from .kannada_asr import date_slots, recover_date, transcribe_kannada
            slots = date_slots(text)
            if slots and slots["day"] and (uncertain or not slots["year"]):
                try:
                    secondary, confidence = transcribe_kannada(tmp_path, MODEL_DIR)
                    recovery = recover_date(text, secondary, confidence)
                except (ImportError, OSError, RuntimeError, ValueError):
                    # The optional local model may not be installed. Retain
                    # clarification rather than using a guessed historical date.
                    recovery = None
                if recovery:
                    recovery["primary_text"] = text
                    text = recovery["text"]
                    uncertain = False
        return {
            **({"recognition_method": "local-kannada-date-consensus", **recovery} if recovery else {}),
            "needs_confirmation": bool(uncertain),
            "text": text,
            "language": getattr(info, "language", language_id) or "en",
            "detected_language": getattr(info, "language", language_id),
            "language_probability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 3),
            "engine": "faster-whisper-local",
            "model": MODEL_NAME,
        }
    finally:
        _transcription_slot.release()
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
    text = speech_text(text, language_id)
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


def speech_text(text: str, language: str) -> str:
    """Expand currency and ISO dates for speech, leaving source names untouched."""
    months = {
        "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"),
        "hi": ("जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"),
        "kn": ("ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್", "ಮೇ", "ಜೂನ್", "ಜುಲೈ", "ಆಗಸ್ಟ್", "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್", "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್"),
    }
    lang = language_code(language)
    def expand(match):
        try:
            d = date.fromisoformat(match[0])
            return f"{d.day} {months[lang][d.month-1]} {d.year}"
        except ValueError:
            return match[0]
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", expand, text)
    currency = {"en": "rupees", "hi": "रुपये", "kn": "ರೂಪಾಯಿ"}[lang]
    text = re.sub(r"₹\s*([\d,]+(?:\.\d+)?)", lambda m: f"{m[1].replace(',', '')} {currency}", text)
    units = {
        "50": {"en": "per 50 kilograms", "hi": "प्रति 50 किलोग्राम", "kn": "ಪ್ರತಿ 50 ಕಿಲೋಗ್ರಾಂ"}[lang],
        "kg": {"en": "per kilogram", "hi": "प्रति किलोग्राम", "kn": "ಪ್ರತಿ ಕಿಲೋಗ್ರಾಂ"}[lang],
        "quintal": {"en": "per quintal", "hi": "प्रति क्विंटल", "kn": "ಪ್ರತಿ ಕ್ವಿಂಟಾಲ್"}[lang],
    }
    for pattern, key in ((r"(?:INR_PER_50KG|Rs\.?\s*/\s*50\s*Kg)", "50"), (r"(?:INR_PER_KG|Rs\.?\s*/\s*Kg)", "kg"), (r"(?:INR_PER_QUINTAL|Rs\.?\s*/\s*Quintal)", "quintal")):
        text = re.sub(pattern, units[key], text, flags=re.I)
    return text
