"""FastAPI router for CropMandi's multilingual voice assistant."""
from __future__ import annotations

from typing import Any, Callable
import logging
import asyncio
from pathlib import Path

from .assistant_service import AssistantService, localize

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .speech_engine import SpeechEngineUnavailable, synthesize_audio_bytes, transcribe_audio_bytes, speech_text

from .intent_parser import parse_command

PriceLookup = Callable[[dict[str, Any]], dict[str, Any] | None]
GeneralHandler = Callable[[dict[str, Any]], dict[str, Any] | str | None]

logger = logging.getLogger(__name__)

MESSAGES = {
    "en": {
        "ask_crop": "Which crop's price would you like to know? For example, coffee, pepper, or cardamom.",
        "ask_market": "Which mandi or market should I check? For example, Chikkamagaluru or Hassan.",
        "ask_variety": "I found multiple price types for that market. Select a variety in the dashboard, or tell me the variety name.",
        "clarify_kal": "In Hindi, 'kal' can mean yesterday or tomorrow. Do you mean yesterday or tomorrow?",
        "no_price": "I couldn't find a recorded {crop} price{where}{when}. Try a market/date available in the data.",
        "price_on": "The recorded {crop} price at {market} on {date} was ₹{price} {unit}.",
        "price_latest": "The latest recorded price for {crop} at {market} was ₹{price} {unit}, dated {date}.",
        "price_not_connected": "The voice command was understood, but the price-data adapter is not connected. Follow the README integration step.",
        "recommendation_missing": "Tell me the crop and location, or choose them in the dashboard first.",
        "recommendation": "The recommendation service suggests: {action}.",
        "weather": "I can help with weather. Please select your state and district first, or open the weather section.",
        "storage": "I'll take you to the cold-storage section.",
        "navigate": "Opening {page}.",
        "route_missing": "I understood the request, but that page's route has not been configured yet.",
        "help": "You can ask for a crop price on a date, nearby cold storage, weather, a sell-or-store recommendation, or ask me to open the dashboard, payments, or settings.",
        "unknown": "I didn't quite understand. Try asking: 'What was the coffee price at Chikkamagaluru APMC on 7 August 2026?'.",
    },
    "hi": {
        "ask_crop": "आप किस फसल का भाव जानना चाहते हैं? उदाहरण: कॉफी, काली मिर्च या इलायची।",
        "ask_market": "किस मंडी या स्थान का भाव देखना है? उदाहरण: चिक्कमगलूरु या हासन।",
        "ask_variety": "इस स्थान के लिए कई किस्मों के भाव मिले हैं। डैशबोर्ड में किस्म चुनें या किस्म का नाम बताइए।",
        "clarify_kal": "हिंदी में 'कल' का अर्थ बीता हुआ कल या आने वाला कल हो सकता है। आप किस दिन की बात कर रहे हैं?",
        "no_price": "दिए गए विवरण{where}{when} के लिए {crop} का भाव नहीं मिला। कृपया उपलब्ध मंडी और तारीख आज़माएँ।",
        "price_on": "{date} को {market} में {crop} का दर्ज भाव ₹{price} {unit} था।",
        "price_latest": "{market} में {crop} का सबसे नया दर्ज भाव ₹{price} {unit} है। डेटा की तारीख {date} है।",
        "price_not_connected": "आपकी बात समझ में आ गई, लेकिन कीमतों का डेटा अभी जोड़ा नहीं गया है। README में दिए integration चरण पूरे करें।",
        "recommendation_missing": "पहले फसल और स्थान बताइए या डैशबोर्ड में चुनिए।",
        "recommendation": "सुझाव सेवा की सलाह है: {action}।",
        "weather": "मौसम की जानकारी के लिए पहले राज्य और जिला चुनें, या मौसम सेक्शन खोलें।",
        "storage": "मैं कोल्ड स्टोरेज सेक्शन खोल रहा हूँ।",
        "navigate": "मैं {page} खोल रहा हूँ।",
        "route_missing": "आपकी बात समझ में आई, लेकिन इस पेज का रास्ता अभी सेट नहीं किया गया है।",
        "help": "आप फसल का भाव और तारीख पूछ सकते हैं, पास का कोल्ड स्टोरेज पूछ सकते हैं, मौसम या बेचने/रखने की सलाह ले सकते हैं, या डैशबोर्ड, भुगतान और सेटिंग्स खोलने को कह सकते हैं।",
        "unknown": "मैं ठीक से समझ नहीं पाया। उदाहरण के लिए पूछें: '7 अगस्त 2026 को चिक्कमगलूरु APMC में कॉफी का भाव क्या था?'",
    },
    "kn": {
        "ask_crop": "ಯಾವ ಬೆಳೆ ಬೆಲೆಯನ್ನು ತಿಳಿಯಬೇಕು? ಉದಾಹರಣೆಗೆ ಕಾಫಿ, ಮೆಣಸು ಅಥವಾ ಏಲಕ್ಕಿ.",
        "ask_market": "ಯಾವ ಮಾರುಕಟ್ಟೆ ಅಥವಾ ಸ್ಥಳದ ಬೆಲೆ ಬೇಕು? ಉದಾಹರಣೆಗೆ ಚಿಕ್ಕಮಗಳೂರು ಅಥವಾ ಹಾಸನ.",
        "ask_variety": "ಈ ಸ್ಥಳಕ್ಕೆ ಹಲವು ತಳಿಗಳ ಬೆಲೆಗಳಿವೆ. ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ನಲ್ಲಿ ತಳಿಯನ್ನು ಆಯ್ಕೆಮಾಡಿ ಅಥವಾ ತಳಿಯ ಹೆಸರನ್ನು ಹೇಳಿ.",
        "clarify_kal": "ದಿನಾಂಕವನ್ನು ಸ್ಪಷ್ಟಪಡಿಸಿ. ನಿನ್ನೆದಿನದ ಬೆಲೆಯೇ ಅಥವಾ ನಾಳೆಯ ಅಂದಾಜೇ ಬೇಕು?",
        "no_price": "ನೀಡಿದ ವಿವರಗಳಿಗೆ{where}{when} {crop} ಬೆಲೆಯ ದಾಖಲೆ ಸಿಗಲಿಲ್ಲ. ಡೇಟಾದಲ್ಲಿರುವ ಮಾರುಕಟ್ಟೆ ಮತ್ತು ದಿನಾಂಕವನ್ನು ಪ್ರಯತ್ನಿಸಿ.",
        "price_on": "{date} ರಂದು {market} ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ {crop} ನ ದಾಖಲಾದ ಬೆಲೆ ₹{price} {unit} ಆಗಿತ್ತು.",
        "price_latest": "{market} ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ {crop} ನ ಇತ್ತೀಚಿನ ದಾಖಲಾದ ಬೆಲೆ ₹{price} {unit}. ದಾಖಲೆ ದಿನಾಂಕ {date}.",
        "price_not_connected": "ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಅರ್ಥವಾಗಿದೆ, ಆದರೆ ಬೆಲೆ ಡೇಟಾ ಇನ್ನೂ ಸಂಪರ್ಕಗೊಂಡಿಲ್ಲ. README ಯ integration ಹಂತಗಳನ್ನು ಅನುಸರಿಸಿ.",
        "recommendation_missing": "ಮೊದಲು ಬೆಳೆ ಮತ್ತು ಸ್ಥಳವನ್ನು ಹೇಳಿ ಅಥವಾ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ನಲ್ಲಿ ಆಯ್ಕೆಮಾಡಿ.",
        "recommendation": "ಶಿಫಾರಸು ಸೇವೆಯ ಸಲಹೆ: {action}.",
        "weather": "ಹವಾಮಾನಕ್ಕಾಗಿ ಮೊದಲು ರಾಜ್ಯ ಮತ್ತು ಜಿಲ್ಲೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ ಅಥವಾ ಹವಾಮಾನ ವಿಭಾಗವನ್ನು ತೆರೆಯಿರಿ.",
        "storage": "ಶೀತಗೃಹ ವಿಭಾಗವನ್ನು ತೆರೆಯುತ್ತಿದ್ದೇನೆ.",
        "navigate": "{page} ತೆರೆಯುತ್ತಿದ್ದೇನೆ.",
        "route_missing": "ನಿಮ್ಮ ವಿನಂತಿ ಅರ್ಥವಾಗಿದೆ, ಆದರೆ ಆ ಪುಟದ ಮಾರ್ಗವನ್ನು ಇನ್ನೂ ಹೊಂದಿಸಿಲ್ಲ.",
        "help": "ಬೆಳೆ ಬೆಲೆ ಮತ್ತು ದಿನಾಂಕ, ಹತ್ತಿರದ ಶೀತಗೃಹ, ಹವಾಮಾನ, ಮಾರಾಟ ಅಥವಾ ಸಂಗ್ರಹಣೆ ಸಲಹೆ ಕೇಳಬಹುದು. ಡ್ಯಾಶ್‌ಬೋರ್ಡ್, ಪಾವತಿ ಅಥವಾ ಸೆಟ್ಟಿಂಗ್‌ಗಳನ್ನು ತೆರೆಯಲು ಸಹ ಹೇಳಬಹುದು.",
        "unknown": "ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಸ್ಪಷ್ಟವಾಗಲಿಲ್ಲ. ಉದಾಹರಣೆ: '2026 ಆಗಸ್ಟ್ 7 ರಂದು ಚಿಕ್ಕಮಗಳೂರು APMC ಯಲ್ಲಿ ಕಾಫಿ ಬೆಲೆ ಎಷ್ಟು?'.",
    },
}

PAGE_LABELS = {
    "en": {"dashboard": "the dashboard", "cold_storage": "cold storage", "recommendations": "recommendations", "payments": "payments", "settings": "settings", "home": "the home page", "weather": "weather"},
    "hi": {"dashboard": "डैशबोर्ड", "cold_storage": "कोल्ड स्टोरेज", "recommendations": "सलाह सेक्शन", "payments": "भुगतान सेक्शन", "settings": "सेटिंग्स", "home": "मुख्य पृष्ठ", "weather": "मौसम सेक्शन"},
    "kn": {"dashboard": "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", "cold_storage": "ಶೀತಗೃಹ ವಿಭಾಗ", "recommendations": "ಶಿಫಾರಸು ವಿಭಾಗ", "payments": "ಪಾವತಿ ವಿಭಾಗ", "settings": "ಸೆಟ್ಟಿಂಗ್‌ಗಳು", "home": "ಮುಖಪುಟ", "weather": "ಹವಾಮಾನ ವಿಭಾಗ"},
}


class VoiceCommandRequest(BaseModel):
    """Validated payload accepted by POST /api/voice/command."""
    text: str | None = Field(default=None, max_length=2000)
    query: str | None = Field(default=None, max_length=2000)
    language: str = "en-IN"
    client_date: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "ignore"


class VoiceSpeakRequest(BaseModel):
    """Text to synthesize into an audio response."""
    text: str = Field(..., min_length=1, max_length=3000)
    language: str = "en-IN"

    class Config:
        extra = "ignore"


def _language_key(language: str | None) -> str:
    return language if language in MESSAGES else "en"


def _price_text(price: Any) -> str:
    try:
        value = float(price)
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(price)


def _unit_text(unit: Any, language: str) -> str:
    """Describe the publisher's unit; never assume all crops are priced per quintal."""
    value = str(unit or "").strip()
    normalized = value.casefold().replace("_", " ").replace("/", " ")
    if not value or "not specified" in normalized:
        return {
            "en": "(unit not specified in source data)",
            "hi": "(मूल डेटा में इकाई नहीं दी गई)",
            "kn": "(ಮೂಲ ಡೇಟಾದಲ್ಲಿ ಘಟಕ ನೀಡಿಲ್ಲ)",
        }.get(language, "(unit not specified in source data)")
    if "50 kg" in normalized or "50kg" in normalized:
        return {"en": "per 50 kg", "hi": "प्रति 50 किलोग्राम", "kn": "ಪ್ರತಿ 50 ಕೆ.ಜಿ."}.get(language, "per 50 kg")
    if "quintal" in normalized or "qtl" in normalized:
        return {"en": "per quintal", "hi": "प्रति क्विंटल", "kn": "ಪ್ರತಿ ಕ್ವಿಂಟಾಲ್‌ಗೆ"}.get(language, "per quintal")
    if "per kg" in normalized or " per kg" in f" {normalized}" or "inr per kg" in normalized:
        return {"en": "per kg", "hi": "प्रति किलोग्राम", "kn": "ಪ್ರತಿ ಕೆ.ಜಿ."}.get(language, "per kg")
    return value


def create_voice_router(
    price_lookup: PriceLookup | None = None,
    recommendation_lookup: GeneralHandler | None = None,
    weather_lookup: GeneralHandler | None = None,
    navigation_routes: dict[str, str] | None = None,
    prefix: str = "/api/voice",
) -> APIRouter:
    """Create a FastAPI router for the assistant.

    ``price_lookup`` receives parsed entities (commodity, market, state, district,
    optional ISO arrival_date) and should return a record with a price field.
    The supplied callbacks are synchronous and FastAPI runs the sync handler in
    its worker thread pool.
    """
    router = APIRouter(prefix=prefix, tags=["voice-assistant"])
    routes = {
        "dashboard": "/cropmandi_ai_dashboard/code.html",
        "my_crops": "/cropmandi_ai_my_crops/code.html",
        "harvest_route": "/cropmandi_ai_harvest_route/code.html",
        "mandi_price_ai": "/cropmandi_mandi_price_ai/code.html",
        "analytics": "/cropmandi_ai_analytics/code.html",
        "cold_storage": "/cropmandi_ai_dashboard/code.html#dash-storage-heading",
        "recommendations": "/cropmandi_ai_dashboard/code.html#dash-rec-title",
        "payments": "/cropmandi_ai_dashboard/code.html#dash-pay-button",
        "settings": "/cropmandi_ai_settings/code.html",
        "home": "/index.html",
        "weather": "/cropmandi_ai_dashboard/code.html#dash-weather-temp",
        "calendar": "/cropmandi_ai_farm_calendar/code.html",
        "alerts": "/cropmandi_ai_alert_center/code.html",
    }
    if navigation_routes:
        routes.update(navigation_routes)

    service = AssistantService(price_lookup) if price_lookup else None
    labels = {
        "en": {"my_crops": "My Crops", "harvest_route": "HarvestRoute", "mandi_price_ai": "Mandi Price AI", "analytics": "Analytics", "calendar": "Farm Calendar", "alerts": "Alert Center"},
        "hi": {"my_crops": "मेरी फसलें", "harvest_route": "हार्वेस्ट रूट", "mandi_price_ai": "मंडी प्राइस एआई", "analytics": "एनालिटिक्स", "calendar": "कृषि कैलेंडर", "alerts": "अलर्ट सेंटर"},
        "kn": {"my_crops": "ನನ್ನ ಬೆಳೆಗಳು", "harvest_route": "ಹಾರ್ವೆಸ್ಟ್ ರೂಟ್", "mandi_price_ai": "ಮಂಡಿ ಪ್ರೈಸ್ ಎಐ", "analytics": "ವಿಶ್ಲೇಷಣೆ", "calendar": "ಕೃಷಿ ಕ್ಯಾಲೆಂಡರ್", "alerts": "ಎಚ್ಚರಿಕೆ ಕೇಂದ್ರ"},
    }
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    # Only existing same-origin application pages are navigable.
    routes = {k:v for k,v in routes.items() if v.startswith("/") and not v.startswith("//") and (frontend / v.split("#")[0].lstrip("/")).is_file()}

    @router.get("/health")
    def health() -> dict[str, Any]:
        return {"success": True, "service": "cropmandi-voice-assistant", "framework": "FastAPI", "languages": ["en-IN", "hi-IN", "kn-IN"]}

    @router.post("/transcribe")
    async def transcribe(
        audio: UploadFile = File(...),
        language: str = Form(default="en-IN"),
    ) -> dict[str, Any]:
        """Transcribe a short browser-recorded clip using local Whisper."""
        max_audio_bytes = 15 * 1024 * 1024
        audio_bytes = await audio.read(max_audio_bytes + 1)
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="The recording was empty. Please try again.")
        if len(audio_bytes) > max_audio_bytes:
            raise HTTPException(status_code=413, detail="Recording is too large. Please keep it under 15 MB.")
        try:
            result = await asyncio.wait_for(run_in_threadpool(
                transcribe_audio_bytes,
                audio_bytes,
                language,
                audio.filename,
                audio.content_type,
            ), timeout=90)
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Speech service timed out. Please retry a shorter clip.") from exc
        except SpeechEngineUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            logger.warning(
                "Voice transcription rejected audio: filename=%r content_type=%r bytes=%d error=%s",
                audio.filename, audio.content_type, len(audio_bytes), exc,
            )
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            # Keep the useful stack trace in the Uvicorn terminal. Without this,
            # all decoder/model errors look like the same opaque HTTP 422 in logs.
            logger.exception(
                "Voice transcription failed while decoding audio: filename=%r content_type=%r bytes=%d",
                audio.filename, audio.content_type, len(audio_bytes),
            )
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not decode the recorded audio. The browser may have finalized "
                    "the recording too early. Please retry with a 2–5 second clip; "
                    "the Uvicorn terminal now contains the specific decoder error."
                ),
            ) from exc
        return {"success": True, "data": result}

    @router.post("/speak")
    async def speak(payload: VoiceSpeakRequest) -> Response:
        """Return an MP3 response using a neural voice for the requested language."""
        text = payload.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        try:
            audio_bytes = await asyncio.wait_for(synthesize_audio_bytes(text, payload.language), timeout=12)
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Speech service timed out. Please retry a shorter clip.") from exc
        except SpeechEngineUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store", "Content-Disposition": 'inline; filename="cropmandi-response.mp3"'},
        )

    def command(payload: VoiceCommandRequest) -> dict[str, Any]:
        text = str(payload.text or payload.query or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="text is required")

        language = str(payload.language or "en-IN")
        context = dict(payload.context or {})
        if payload.client_date and not context.get("client_date"):
            context["client_date"] = payload.client_date

        from datetime import date
        if context.get("client_date"):
            try:
                context["client_date"] = date.fromisoformat(str(context["client_date"])).isoformat()
            except ValueError:
                raise HTTPException(status_code=400, detail="client_date must be a valid ISO date")
        parsed = parse_command(text, language, context)
        lang = _language_key(parsed["language"])
        messages = MESSAGES[lang]
        intent = parsed["intent"]
        entities = parsed["entities"]
        reply = messages["unknown"]
        action: dict[str, Any] | None = None
        data: dict[str, Any] = {"intent": intent, "entities": entities}

        service_intents = {"prediction", "compare_prices", "market_rankings", "harvest_route", "cold_storage", "my_crops"}
        if not weather_lookup:
            service_intents.add("weather")
        if not recommendation_lookup:
            service_intents.add("recommendation")
        result = None
        inventory_reply = None
        if service and intent in ("price_lookup", "prediction") and not entities.get("invalid_date") and not entities.get("date_ambiguous") and not entities.get("date_unresolved"):
            try:
                inventory_reply = service.inventory_context(entities, lang)
            except Exception:
                logger.exception("Voice inventory context unavailable")
        if inventory_reply:
            data.update(inventory_reply)
            reply = inventory_reply["answer"]
        elif entities.get("date_unresolved"):
            reply = localize(lang, "I couldn't resolve that date reliably. Please say or type the full day, month and year.", "तारीख स्पष्ट नहीं समझ पाया। कृपया पूरा दिन, महीना और साल बोलें या लिखें।", "ದಿನಾಂಕ ಸ್ಪಷ್ಟವಾಗಿ ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಪೂರ್ಣ ದಿನ, ತಿಂಗಳು ಮತ್ತು ವರ್ಷ ಹೇಳಿ ಅಥವಾ ಬರೆಯಿರಿ.")
            data["needs_clarification"] = True
        elif entities.get("invalid_date"):
            reply = localize(lang, "That date is invalid. Please provide a valid day, month and year.", "तारीख मान्य नहीं है। दिन, महीना और साल स्पष्ट बताइए।", "ಆ ದಿನಾಂಕ ಮಾನ್ಯವಲ್ಲ. ಸರಿಯಾದ ದಿನ, ತಿಂಗಳು ಮತ್ತು ವರ್ಷ ತಿಳಿಸಿ.")
            data["needs_clarification"] = True
        elif entities.get("date_ambiguous"):
            reply = messages["clarify_kal"]
            data["needs_clarification"] = True
        elif intent in service_intents:
            try:
                result = service(intent, entities, lang) if service else None
            except Exception:
                logger.exception("Voice service failed: %s", intent)
                result = {"answer": localize(lang, "The data service is unavailable or timed out. Please retry. No price or result was substituted.", "डेटा सेवा उपलब्ध नहीं है या समय सीमा पूरी हुई। फिर कोशिश करें। कोई वैकल्पिक भाव नहीं दिया गया।", "ಡೇಟಾ ಸೇವೆ ಲಭ್ಯವಿಲ್ಲ ಅಥವಾ ಸಮಯ ಮೀರಿದೆ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ. ಬೇರೆ ಬೆಲೆ ಅಥವಾ ಫಲಿತಾಂಶ ಬಳಸಿಲ್ಲ."), "service_error": True}
            if result:
                data.update(result)
                reply = result["answer"]
            else:
                reply = messages["price_not_connected"]
        elif intent == "price_lookup":
            commodity = entities.get("commodity")
            market = entities.get("market")
            requested_date = entities.get("arrival_date")
            if entities.get("date_ambiguous"):
                reply = messages["clarify_kal"]
            elif not commodity:
                reply = messages["ask_crop"]
            elif not market:
                reply = messages["ask_market"]
            elif not price_lookup:
                reply = messages["price_not_connected"]
                action = {"type": "lookup_price", "params": entities}
            else:
                try:
                    record = price_lookup({**entities, "commodity": commodity, "arrival_date": requested_date})
                except Exception:
                    logger.exception("Voice price lookup failed")
                    record = {"service_error": True}
                if record and record.get("service_error"):
                    reply = localize(lang, "The price service is unavailable. Please retry.", "भाव सेवा उपलब्ध नहीं है। फिर कोशिश करें।", "ಬೆಲೆ ಸೇವೆ ಲಭ್ಯವಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.")
                    data["service_error"] = True
                elif record and record.get("needs_variety"):
                    data["needs_clarification"] = True
                    reply = messages["ask_variety"]
                    data["available_series"] = record.get("available_series", [])
                    reply += " " + ", ".join(str(x) for x in data["available_series"][:5])
                elif not record:
                    where = f" at {market}" if lang == "en" else f" {market} में" if lang == "hi" else f" {market} ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ"
                    when = f" on {requested_date}" if requested_date and lang == "en" else f" {requested_date} को" if requested_date and lang == "hi" else f" {requested_date} ರಂದು" if requested_date and lang == "kn" else ""
                    reply = messages["no_price"].format(crop=commodity.title(), where=where, when=when)
                else:
                    price = record.get("modal_price", record.get("current_price", record.get("price", record.get("price_per_qtl"))))
                    record_date = record.get("arrival_date") or requested_date or "date unavailable"
                    display_market = record.get("market") or market
                    crop_label = " ".join(str(x) for x in (record.get("commodity") or commodity, record.get("series"), record.get("grade")) if x)
                    unit = _unit_text(record.get("unit"), lang)
                    count = record.get("record_count")
                    if requested_date:
                        reply = messages["price_on"].format(crop=crop_label, market=display_market, date=record_date, price=_price_text(price), unit=unit)
                    else:
                        reply = messages["price_latest"].format(crop=crop_label, market=display_market, date=record_date, price=_price_text(price), unit=unit)
                    if isinstance(count, int) and count > 1:
                        count_note = f" (median of {count} matching records)" if lang == "en" else f"（{count} संबंधित रिकॉर्ड का मध्य मान）" if lang == "hi" else f"（{count} ಹೊಂದಾಣಿಕೆಯ ದಾಖಲೆಗಳ ಮಧ್ಯಕ）"
                        reply += count_note
                    status = str(record.get("data_status") or "").upper()
                    usage = str(record.get("data_usage") or "").upper()
                    if "UNVERIFIED" in status or "EXPERIMENTAL_ONLY" in usage or "LOCAL_MARKET_CENTRE_DATA" in usage:
                        caution = {
                            "en": " Note: this is unverified local/experimental data; confirm it before making a sale.",
                            "hi": " ध्यान दें: यह अप्रमाणित स्थानीय/प्रायोगिक डेटा है; बिक्री का निर्णय लेने से पहले इसकी पुष्टि करें।",
                            "kn": " ಗಮನಿಸಿ: ಇದು ಪರಿಶೀಲಿಸದ ಸ್ಥಳೀಯ/ಪ್ರಾಯೋಗಿಕ ಡೇಟಾ; ಮಾರಾಟದ ನಿರ್ಧಾರಕ್ಕೂ ಮೊದಲು ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ.",
                        }.get(lang, " Note: this is unverified data; confirm it before making a sale.")
                        reply += caution
                    data["price_record"] = record
                    action = {"type": "show_price", "record": record}

        elif intent == "navigate":
            target = entities.get("navigation_target") or "dashboard"
            path = routes.get(target)
            if target == "back":
                reply = localize(lang, "Returning to the previous page.", "पिछले पेज पर जा रहा हूँ।", "ಹಿಂದಿನ ಪುಟಕ್ಕೆ ಹಿಂತಿರುಗುತ್ತಿದ್ದೇನೆ.")
                action = {"type": "back"}
            elif path:
                reply = messages["navigate"].format(page=labels[lang].get(target) or PAGE_LABELS[lang].get(target, target))
                action = {"type": "navigate", "target": target, "path": path}
            else:
                reply = messages["route_missing"]

        elif intent == "cold_storage":
            path = routes.get("cold_storage")
            reply = messages["storage"] if path else messages["route_missing"]
            if path:
                action = {"type": "navigate", "target": "cold_storage", "path": path}

        elif intent == "weather":
            if weather_lookup:
                try:
                    result = weather_lookup(entities) or {}
                except Exception:
                    result = {}
                data["weather"] = result
                reply = str(result.get("answer") or result.get("message") or messages["weather"])
            else:
                path = routes.get("weather")
                reply = messages["weather"]
                if path:
                    action = {"type": "navigate", "target": "weather", "path": path}

        elif intent == "recommendation":
            if recommendation_lookup:
                try:
                    result = recommendation_lookup(entities) or {}
                except Exception:
                    result = {}
                data["recommendation"] = result
                recommendation = result.get("action") or result.get("recommendation") or result.get("decision")
                if recommendation:
                    reply = messages["recommendation"].format(action=str(recommendation))
                else:
                    reply = messages["recommendation_missing"]
            else:
                path = routes.get("recommendations")
                reply = messages["recommendation_missing"]
                if path:
                    action = {"type": "navigate", "target": "recommendations", "path": path}

        elif intent == "help":
            reply = messages["help"]

        if intent == "price_lookup" and (not entities.get("commodity") or not entities.get("market")):
            data["needs_clarification"] = True
        # Return bounded structured memory, not a growing transcript or global session.
        conversation = {k: entities[k] for k in ("commodity", "market", "variety", "grade", "quantity", "quantity_unit", "origin", "vehicle_mode", "vehicle_id", "ownership", "forecast_date") if entities.get(k) is not None}
        conversation["last_intent"] = intent
        if data.get("needs_clarification"):
            conversation["pending_intent"] = intent
            if data.get("available_series"):
                conversation["choices"] = data["available_series"][:10]
            if entities.get("arrival_date"):
                conversation["target_date"] = entities["arrival_date"]
        return {
            "success": True,
            "data": {
                "answer": reply,
                "spoken_answer": speech_text(reply, lang),
                "conversation": conversation,
                "language": parsed["language"],
                "intent": intent,
                "confidence": parsed["confidence"],
                "entities": entities,
                "action": action,
                **data,
            },
        }

    @router.post("/command")
    async def command_endpoint(payload: VoiceCommandRequest):
        try:
            return await asyncio.wait_for(run_in_threadpool(command, payload), timeout=40)
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail="The data request timed out. Please retry.") from exc

    return router
