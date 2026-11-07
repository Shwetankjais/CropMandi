"""Voice-only contracts, including read-only integration with the real project data."""
from datetime import date
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from cropmandi.db.models import CropMarketObservation as Obs
from cropmandi_voice_assistant import create_voice_router
from cropmandi_voice_assistant.project_adapter import make_project_price_lookup
from cropmandi_voice_assistant.intent_parser import parse_command
from cropmandi_voice_assistant.speech_engine import speech_text, SpeechEngineUnavailable

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def factory():
    engine = create_engine(f"sqlite:///file:{ROOT / 'data/cropmandi.db'}?mode=ro&uri=true", connect_args={"check_same_thread": False})
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture(scope="module")
def client(factory):
    app = FastAPI()
    app.include_router(create_voice_router(price_lookup=make_project_price_lookup(factory)))
    return TestClient(app)


def command(client, text, **context):
    response = client.post("/api/voice/command", json={"text": text, "language": "auto", "client_date": "2026-11-07", "context": context})
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.parametrize("text,target", [
    ("Open Dashboard", "dashboard"), ("Go to My Crops", "my_crops"), ("Open Harvest Route", "harvest_route"),
    ("Show Mandi Price AI", "mandi_price_ai"), ("Open Analytics", "analytics"), ("Go to Cold Storage", "cold_storage"),
    ("Open Settings", "settings"), ("Go back to the previous page", "back"), ("Open Farm Calendar", "calendar"), ("Open Alerts", "alerts"),
    ("मेरी फसलें खोलो", "my_crops"), ("हार्वेस्ट रूट खोलो", "harvest_route"), ("एनालिटिक्स खोलो", "analytics"), ("कोल्ड स्टोरेज खोलो", "cold_storage"),
    ("ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ತೆರೆಯಿರಿ", "dashboard"), ("ನನ್ನ ಬೆಳೆಗಳು ತೆರೆಯಿರಿ", "my_crops"), ("ಹಾರ್ವೆಸ್ಟ್ ರೂಟ್ ತೆರೆಯಿರಿ", "harvest_route"), ("ಮಂಡಿ ಪ್ರೈಸ್ ತೆರೆಯಿರಿ", "mandi_price_ai"),
    ("Open harvest root", "harvest_route"),
])
def test_navigation_existing_pages(client, text, target):
    data = command(client, text)
    assert data["intent"] == "navigate"
    if target == "back":
        assert data["action"]["type"] == "back"
    else:
        assert data["action"]["target"] == target
        path = data["action"]["path"].split("#")[0]
        assert (ROOT / "frontend" / path.lstrip("/")).is_file()


@pytest.mark.parametrize("text,language,expected", [
    ("coffee price yesterday", "en", "2026-11-06"),
    ("ಇವತ್ತಿನ ಕಾಫಿ ಬೆಲೆ ಎಷ್ಟು?", "kn", "2026-11-07"),
    ("ನಿನ್ನೆ ಕಾಫಿ ಬೆಲೆ", "kn", "2026-11-06"),
    ("१५ अक्टूबर २०२६ को कॉफी का भाव", "hi", "2026-10-15"),
    ("೧೫ ಅಕ್ಟೋಬರ್ ೨೦೨೬ ಕಾಫಿ ಬೆಲೆ", "kn", "2026-10-15"),
    ("coffee price on 2026-10-15", "en", "2026-10-15"),
])
def test_multilingual_dates(text, language, expected):
    data = parse_command(text, "auto", {"client_date": "2026-11-07"})
    assert data["language"] == language
    assert data["entities"]["arrival_date"] == expected


@pytest.mark.parametrize("crop", ["tomato", "potato", "paddy", "maize"])
def test_real_exact_historical_and_latest_prices(factory, client, crop):
    with factory() as session:
        row = session.scalars(select(Obs).where(Obs.crop_code == crop).order_by(Obs.market_date.desc())).first()
        context = dict(commodity=crop, market=row.market_name, variety=row.variety, grade=row.grade)
        data = command(client, f"{crop} price on {row.market_date}", **context)
        assert data["price_record"]["price"] == float(row.modal_price)
        assert data["price_record"]["arrival_date"] == row.market_date.isoformat()
        latest = command(client, f"latest {crop} price", **context)
        assert latest["price_record"]["arrival_date"] == row.market_date.isoformat()
        assert "latest recorded" in latest["answer"]
        assert "unverified" in latest["answer"].lower()
        missing = command(client, f"{crop} price today", **context)
        assert "price_record" not in missing
        wrong = command(client, f"{crop} price on {row.market_date}", **{**context,"market":"NO_SUCH_MARKET"})
        assert "price_record" not in wrong


def test_forecast_reuses_actual_existing_model(client):
    from apps.api.mandi_price_ai import predict_price
    data = command(client, "Predict tomorrow tomato price at Kolar")
    assert data["intent"] == "prediction"
    assert data["forecast"]["price"] == predict_price("tomato", "KOLAR", "2026-11-08")
    assert data["forecast"]["kind"] == "recursive_market_estimate"
    assert data["forecast"]["input_date"] < data["forecast"]["prediction_date"]
    assert "variety/grade" in data["answer"]
    week = command(client, "Predict next week tomato price at Kolar")
    assert week["forecast"]["prediction_date"] == "2026-11-14"
    assert week["forecast"]["price"] == predict_price("tomato", "KOLAR", "2026-11-14")


def test_forecast_never_uses_shared_benchmark_fallback(client):
    with patch("ml.unified_prediction_service.predict_price", side_effect=AssertionError("Do not call fallback-prone path")):
        data = command(client, "Predict tomorrow tomato price", commodity="tomato", market="NO_SUCH_MARKET")
        assert "forecast" not in data
        assert "No matching data" in data["answer"]


def test_followup_preserves_requested_date_and_entities(client):
    first = command(client, "coffee price on 15 October 2026")
    assert first["needs_clarification"]
    second = command(client, "Hassan", **first["conversation"])
    assert second["entities"]["arrival_date"] == "2026-10-15"
    assert second["entities"]["commodity"] == "coffee"
    assert second["entities"]["market"] == "Hassan"


def test_followup_crop_change_drops_incompatible_variety():
    data = parse_command("what about tomato price", "en-IN", {"commodity":"coffee", "variety":"Arabica Parchment"})
    assert data["entities"]["commodity"] == "tomato"
    assert data["entities"]["variety"] is None


def test_hindi_ambiguous_day_never_predicts(client):
    data = command(client, "कल कॉफी का भाव बताओ", commodity="coffee", market="Hassan")
    assert data["needs_clarification"]
    assert "price_record" not in data and "forecast" not in data


def test_invalid_date_not_latest(client):
    data = command(client, "coffee price at Hassan on 31 February 2026")
    assert data["needs_clarification"]
    assert "invalid" in data["answer"]


def test_service_exception_not_reported_as_missing_data(client):
    with patch("apps.api.weather.weather_payload", side_effect=TimeoutError):
        data = command(client, "weather at Hassan")
        assert data["service_error"]
        assert "unavailable" in data["answer"]


def test_no_invented_sell_wait_store_recommendation(client):
    data = command(client, "should I sell coffee now?")
    assert "No connected service" in data["answer"]
    assert data["action"] is None


def test_real_inventory(client):
    data = command(client, "show my crops")
    assert data["inventory_count"] == 9
    assert "coffee" in data["answer"]


def test_comparison_uses_matching_actual_records(factory, client):
    with factory() as session:
        row = session.scalars(select(Obs).where(Obs.crop_code == "tomato", Obs.market_name == "KOLAR").order_by(Obs.market_date.desc())).first()
        data = command(client, "Compare tomato prices on 15 October 2026", commodity="tomato",market=row.market_name,variety=row.variety,grade=row.grade)
        assert len(data["records"]) == 2
        assert data["records"][0] and data["records"][1]
        assert data["difference"] == data["records"][0]["price"] - data["records"][1]["price"]


def test_harvest_route_existing_calculations_with_real_prices(client):
    # Only the network distance lookup is replaced; real prices, vehicle costs
    # and net-realization calculations still run in the existing service.
    with patch("apps.api.harvest_routes._road_route", return_value={"distance_km":42.0,"duration_min":60,"geometry":None}):
        data = command(client, "What is the transport cost for 500 kg coffee from Hassan?", variety="Arabica Parchment")
    assert data["intent"] == "harvest_route"
    assert data["route"]["quantity_kg"] == 500
    best = data["route"]["markets"][0]
    assert best["distance_km"] == 42
    assert best["net_estimate_inr"] == best["profit_breakdown"]["net_realization"]
    assert best["transport_estimate_inr"] == best["profit_breakdown"]["total_transport_cost"]
    assert str(best["price_date"]) in data["answer"]


@pytest.mark.parametrize("lang,month,currency", [("en","October","rupees"),("hi","अक्टूबर","रुपये"),("kn","ಅಕ್ಟೋಬರ್","ರೂಪಾಯಿ")])
def test_speech_dates_currency(lang, month, currency):
    text = speech_text("2026-10-15 ₹25,000 Arabica Parchment", lang)
    assert month in text and currency in text
    assert "Arabica Parchment" in text and "₹" not in text


def test_speech_failure_status_and_empty_audio(client):
    with patch("cropmandi_voice_assistant.routes.synthesize_audio_bytes", new_callable=AsyncMock, side_effect=SpeechEngineUnavailable("offline")):
        assert client.post("/api/voice/speak", json={"text":"ನಮಸ್ಕಾರ", "language":"kn-IN"}).status_code == 503
    assert client.post("/api/voice/transcribe", files={"audio":("clip.webm",b"","audio/webm")}).status_code == 400


def test_no_unknown_route_even_when_misconfigured():
    app=FastAPI();app.include_router(create_voice_router(navigation_routes={"dashboard":"/missing/page.html"}))
    data = command(TestClient(app), "Open dashboard")
    assert data["action"] is None


def test_harvest_page_only_widget_includes_changed():
    import subprocess
    original = subprocess.check_output(["git","show","HEAD:frontend/cropmandi_ai_harvest_route/code.html"], cwd=ROOT, text=True)
    current = (ROOT / "frontend/cropmandi_ai_harvest_route/code.html").read_text()
    assert current.replace('  <link rel="stylesheet" href="../styles/voice-assistant.css?v=voice-3"/>\n', '').replace('  <script src="../js/voice-assistant.js?v=voice-3" defer></script>\n','') == original


@pytest.mark.parametrize("text", ["coffee price on 31 February 2026", "कॉफी का भाव ३१ फरवरी २०२६", "ಕಾಫಿ ಬೆಲೆ ೩೧ ಫೆಬ್ರವರಿ ೨೦೨೬"])
def test_invalid_native_dates_never_become_latest(client, text):
    data = command(client, text, commodity="coffee", market="Hassan")
    assert data["needs_clarification"]
    assert "price_record" not in data


def test_two_explicit_comparison_dates(client):
    data = command(client, "Compare tomato price at Kolar on 15 October 2026 and 20 October 2026")
    assert [r["arrival_date"] for r in data["records"]] == ["2026-10-15", "2026-10-20"]


def test_my_crops_context_and_ambiguity(client):
    ambiguous = command(client, "coffee price", page="/cropmandi_ai_my_crops/code.html")
    assert ambiguous["needs_clarification"] and "several matching crops" in ambiguous["answer"]
    unique = command(client, "pepper price", page="/cropmandi_ai_my_crops/code.html")
    assert unique["entities"]["market"] == "Madikeri"
    assert unique["entities"]["variety"] == "Cochin Garbled"
    assert unique["entities"]["quantity"] == 20


def test_grade_and_variety_followup_uses_returned_options():
    data = parse_command("HYBRID/LOCAL / SMALL", "en-IN", {"commodity":"maize","market":"HAVERI","pending_intent":"price_lookup","last_intent":"price_lookup","target_date":"2026-10-15","choices":["HYBRID/LOCAL / SMALL"]})
    assert data["entities"]["variety"] == "HYBRID/LOCAL"
    assert data["entities"]["grade"] == "SMALL"
    assert data["entities"]["arrival_date"] == "2026-10-15"


@pytest.mark.parametrize("transcript,language", [("मुझे आज का कॉफी का भाव बताओ।","hi-IN"),("ಇವತ್ತಿನ ಕಾಪಿ ಬಿಲೆಯೆಷ್ಟು, ಇವತ್ತಿನ ಕಾಪಿ ಬಿಲೆಯೆಷ್ಟು.","kn-IN")])
def test_observed_turbo_transcripts_recover_price_entities(transcript, language):
    data = parse_command(transcript, language, {"client_date":"2026-11-07"})
    assert data["intent"] == "price_lookup"
    assert data["entities"]["commodity"] == "coffee"
    assert data["entities"]["arrival_date"] == "2026-11-07"


def wav_bytes(seconds=1):
    import io, wave
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(8000)
        out.writeframes(b"\0\0" * (8000 * seconds))
    return buffer.getvalue()


def test_transcription_decodes_audio_and_flags_wrong_script():
    from types import SimpleNamespace
    from cropmandi_voice_assistant.speech_engine import transcribe_audio_bytes
    model = SimpleNamespace(transcribe=lambda *_args, **_kwargs: ([SimpleNamespace(text="कॉफी भाव",avg_logprob=-0.1,compression_ratio=1.0)],SimpleNamespace(language="kn",language_probability=1.0)))
    with patch("cropmandi_voice_assistant.speech_engine._get_whisper_model", return_value=model):
        data = transcribe_audio_bytes(wav_bytes(), "kn-IN", "clip.wav", "audio/wav")
    assert data["needs_confirmation"] is True


def test_transcription_rejects_long_audio_before_loading_model():
    from cropmandi_voice_assistant.speech_engine import transcribe_audio_bytes
    with patch("cropmandi_voice_assistant.speech_engine._get_whisper_model") as model:
        with pytest.raises(ValueError, match="too long"):
            transcribe_audio_bytes(wav_bytes(36), "en-IN", "clip.wav", "audio/wav")
        model.assert_not_called()


def test_transcription_busy_fails_cleanly():
    from cropmandi_voice_assistant import speech_engine
    speech_engine._transcription_slot.acquire()
    try:
        with pytest.raises(SpeechEngineUnavailable, match="busy"):
            speech_engine.transcribe_audio_bytes(wav_bytes())
    finally:
        speech_engine._transcription_slot.release()


def test_selected_forecast_date_and_origin_defaults():
    parsed = parse_command("predict the price", "en-IN", {"commodity":"tomato","market":"KOLAR","forecast_date":"2026-11-12","client_date":"2026-11-07"})
    assert parsed["entities"]["arrival_date"] == "2026-11-12"
    parsed = parse_command("coffee price", "en-IN", {"origin":"Sakleshpur, Hassan"})
    assert parsed["entities"]["market"] == "Sakleshpur"


def test_spoken_weather_location_overrides_page_origin(client):
    with patch("apps.api.weather.weather_payload", return_value={"location":"Kolar","temperature_c":25,"humidity_percent":60,"description":"Clear"}) as weather:
        data = command(client, "weather at Kolar", origin="Sakleshpur, Hassan")
        weather.assert_called_once_with("Kolar")
        assert "Kolar" in data["answer"]


def test_decimal_harvest_quantity_is_not_mistaken_for_a_date():
    data = parse_command("transport cost for 500.5 kg coffee from Hassan", "en-IN", {})
    assert data["intent"] == "harvest_route"
    assert not data["entities"]["invalid_date"]
    assert data["entities"]["quantity"] == 500.5


def test_truncated_transcript_requires_confirmation():
    from types import SimpleNamespace
    from cropmandi_voice_assistant.speech_engine import transcribe_audio_bytes
    segment = SimpleNamespace(text="partial query",avg_logprob=-0.1,compression_ratio=1.0,tokens=list(range(128)))
    model = SimpleNamespace(transcribe=lambda *_args,**_kwargs:([segment],SimpleNamespace(language="en",language_probability=1.0)))
    with patch("cropmandi_voice_assistant.speech_engine._get_whisper_model", return_value=model):
        assert transcribe_audio_bytes(wav_bytes(),"en-IN","clip.wav")["needs_confirmation"]
