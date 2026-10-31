"""Tests for the Mandi Price AI multi-crop prediction pipeline."""
from __future__ import annotations

from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_mandi_price_health():
    response = client.get("/api/mandi-price/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["model_ready"] is True
    assert data["datasets_ready"] is True
    assert sorted(data["supported_crops"]) == ["maize", "paddy", "potato", "tomato"]


def test_mandi_price_markets_listing():
    for crop in ["paddy", "tomato", "potato", "maize"]:
        response = client.get(f"/api/mandi-price/markets?crop={crop}")
        assert response.status_code == 200
        data = response.json()
        assert data["crop"] == crop
        assert data["count"] > 0
        assert len(data["markets"]) > 0


def test_mandi_price_predict_historical_and_future():
    # Test Paddy at Malavalli
    response = client.post("/api/mandi-price/predict", json={
        "crop": "paddy",
        "market": "MALAVALLI",
        "target_date": "2026-10-29",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["crop"] == "paddy"
    assert data["market"] == "MALAVALLI"
    assert float(data["predicted_modal_price"]) > 0

    # Test future date
    future_response = client.post("/api/mandi-price/predict", json={
        "crop": "paddy",
        "market": "MALAVALLI",
        "target_date": "2026-11-05",
    })
    assert future_response.status_code == 200
    assert float(future_response.json()["predicted_modal_price"]) > 0


def test_mandi_price_crops_summary():
    response = client.get("/api/mandi-price/crops/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["model_ready"] is True
    assert len(data["crops"]) == 4

