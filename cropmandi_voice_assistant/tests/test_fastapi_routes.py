import unittest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cropmandi_voice_assistant import create_voice_router


class FastAPIRouteTests(unittest.TestCase):
    def setUp(self):
        def price_lookup(params):
            if (params.get("commodity") or "").lower() == "coffee" and params.get("market") == "Chikkamagaluru APMC":
                return {
                    "commodity": "Coffee",
                    "market": "Chikkamagaluru APMC",
                    "arrival_date": params.get("arrival_date") or "2026-08-07",
                    "modal_price": 30000,
                    "unit": "per quintal",
                }
            return None

        app = FastAPI()
        app.include_router(create_voice_router(price_lookup=price_lookup))
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/api/voice/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn("FastAPI", response.json()["framework"])

    def test_price_command(self):
        response = self.client.post("/api/voice/command", json={
            "text": "What was the coffee price at Chikkamagaluru APMC on 7 August 2026?",
            "language": "en-IN",
            "client_date": "2026-10-25",
            "context": {},
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["intent"], "price_lookup")
        self.assertIn("30,000", body["data"]["answer"])

    def test_navigation_command(self):
        response = self.client.post("/api/voice/command", json={
            "text": "Open the dashboard", "language": "en-IN"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["action"]["type"], "navigate")

    def test_empty_command_rejected(self):
        response = self.client.post("/api/voice/command", json={"text": "   "})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "text is required")

    @patch("cropmandi_voice_assistant.routes.transcribe_audio_bytes")
    def test_transcribe_endpoint_accepts_recorded_audio(self, transcribe):
        transcribe.return_value = {
            "text": "कॉफी का भाव क्या है",
            "language": "hi",
            "detected_language": "hi",
            "language_probability": 0.98,
            "engine": "faster-whisper-local",
            "model": "base",
        }
        response = self.client.post(
            "/api/voice/transcribe",
            files={"audio": ("speech.webm", b"fake-audio-bytes", "audio/webm")},
            data={"language": "hi-IN"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIn("कॉफी", body["data"]["text"])
        transcribe.assert_called_once()

    @patch("cropmandi_voice_assistant.routes.synthesize_audio_bytes", new_callable=AsyncMock)
    def test_speak_endpoint_returns_mp3(self, synthesize):
        synthesize.return_value = b"fake-mp3-data"
        response = self.client.post(
            "/api/voice/speak",
            json={"text": "ನಮಸ್ಕಾರ", "language": "kn-IN"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "audio/mpeg")
        self.assertEqual(response.content, b"fake-mp3-data")
        synthesize.assert_awaited_once_with("ನಮಸ್ಕಾರ", "kn-IN")

    def test_unverified_price_reply_preserves_unit_and_warning(self):
        def lookup(_params):
            return {
                "commodity": "coffee",
                "market": "Chikkamagaluru",
                "arrival_date": "2026-08-27",
                "price": 25850,
                "unit": "Rs./50 Kg",
                "data_status": "UNVERIFIED_LOCAL_DATA",
            }

        app = FastAPI()
        app.include_router(create_voice_router(price_lookup=lookup))
        client = TestClient(app)
        response = client.post("/api/voice/command", json={
            "text": "What was the coffee price at Chikkamagaluru on 27 August 2026?",
            "language": "en-IN",
            "context": {},
        })
        self.assertEqual(response.status_code, 200)
        answer = response.json()["data"]["answer"]
        self.assertIn("per 50 kg", answer)
        self.assertIn("unverified", answer.lower())


if __name__ == "__main__":
    unittest.main()
