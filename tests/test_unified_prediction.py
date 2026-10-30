"""
Unit and integration tests for the unified ML prediction service and multi-crop endpoints.
Tests best_price_model.joblib integration, baseline models, persistence, and validation.
"""
from __future__ import annotations

import math
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def restore_session_factory():
    import apps.api.main as api_main
    from cropmandi.db.session import make_session_factory
    factory = make_session_factory()
    api_main.SessionLocal = factory
    api_main.app.state.session_factory = factory
    yield



def test_commodities_list_returns_all_six_commodities():
    res = client.get("/api/commodities/list")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    commodities = data["commodities"]
    assert len(commodities) == 6
    codes = {c["code"] for c in commodities}
    assert codes == {"coffee", "pepper", "potato", "tomato", "maize", "paddy"}

    # Verify best_price_model crops are marked ML_PREDICTION and READY
    for c in commodities:
        if c["code"] in {"potato", "tomato", "maize", "paddy"}:
            assert c["status"] == "READY"
            assert c["model_type"] == "ML_PREDICTION"
        elif c["code"] in {"coffee", "pepper"}:
            assert c["status"] == "AVAILABLE"
            assert c["model_type"] == "BASELINE_ESTIMATE"


def test_commodity_options_returns_dynamic_markets_and_varieties():
    for crop in ("potato", "tomato", "maize", "paddy"):
        res = client.get("/api/commodities/options", params={"commodity": crop})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert len(data["varieties"]) > 0
        assert len(data["markets"]) > 0
        assert len(data["locations"]) > 0
        assert "district" in data["locations"][0]

    # Also coffee and pepper options
    for crop in ("coffee", "pepper"):
        res = client.get("/api/commodities/options", params={"commodity": crop})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert len(data["varieties"]) > 0
        assert len(data["markets"]) > 0


def test_best_price_model_predictions_for_all_four_vegetable_crops():
    vegetables = [
        ("potato", "Jyothi", "BENGALURU"),
        ("tomato", "Hybrid", "KOLAR"),
        ("maize", "Local", "ARAKALGUD"),
        ("paddy", "Sona Masuri", "SHIVAMOGGA"),
    ]
    for crop, variety, market in vegetables:
        payload = {
            "commodity": crop,
            "variety": variety,
            "market": market,
            "prediction_date": "2026-11-05",
            "quantity": 50.0,
            "quantity_unit": "quintal",
        }
        res = client.post("/api/predictions/price", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        assert data["crop_code"] == crop
        assert math.isfinite(data["predicted_price"])
        assert data["predicted_price"] > 0
        assert math.isfinite(data["latest_observed_price"])
        assert data["latest_observed_price"] > 0
        assert data["model_name"] == "ExtraTreesRegressor Pipeline"
        assert data["model_status"] == "READY"
        assert data["prediction_type"] == "ML prediction"
        assert data["estimated_gross_value"] == round(data["predicted_price"] * 50.0, 2)
        assert data["quantity"] == 50.0
        assert "features_used" in data
        assert "modal_today" in data["features_used"]
        assert "crop" in data["features_used"]
        assert data["features_used"]["crop"] == crop.upper()


def test_baseline_predictions_for_coffee_and_pepper():
    # Coffee
    coffee_res = client.post("/api/predictions/price", json={
        "commodity": "coffee",
        "variety": "Arabica Parchment",
        "market": "Somwarpet",
        "prediction_date": "2026-11-05",
        "quantity": 25.0,
    })
    assert coffee_res.status_code == 200
    c_data = coffee_res.json()
    assert c_data["success"] is True
    assert c_data["crop_code"] == "coffee"
    assert c_data["predicted_price"] > 0
    assert c_data["model_name"] == "Naive Last-Value Baseline"
    assert c_data["prediction_type"] == "Baseline estimate"

    # Pepper
    pepper_res = client.post("/api/predictions/price", json={
        "commodity": "pepper",
        "variety": "Cochin Garbled",
        "market": "Kochi",
        "prediction_date": "2026-11-05",
        "quantity": 10.0,
    })
    assert pepper_res.status_code == 200
    p_data = pepper_res.json()
    assert p_data["success"] is True
    assert p_data["crop_code"] == "pepper"
    assert p_data["predicted_price"] > 0


def test_cardamom_returns_pending_data_feed():
    res = client.post("/api/predictions/price", json={
        "commodity": "cardamom",
        "variety": "Small Cardamom",
        "market": "Bodinayakanur",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["model_status"] == "PENDING_DATA_SOURCE"
    assert "pending" in data["message"].lower()


def test_invalid_prediction_inputs():
    # Invalid date format
    bad_date = client.post("/api/predictions/price", json={
        "commodity": "potato",
        "variety": "Jyothi",
        "market": "BENGALURU",
        "prediction_date": "invalid-date",
    })
    assert bad_date.status_code == 400

    # Negative quantity
    bad_qty = client.post("/api/predictions/price", json={
        "commodity": "potato",
        "variety": "Jyothi",
        "market": "BENGALURU",
        "quantity": -10,
    })
    assert bad_qty.status_code == 400


def test_prediction_history_persists_and_retrieves_audit_log():
    # Submit prediction
    post_res = client.post("/api/predictions/price", json={
        "commodity": "potato",
        "variety": "Jyothi",
        "market": "BENGALURU",
        "prediction_date": "2026-11-10",
        "quantity": 100.0,
    })
    assert post_res.status_code == 200
    pred = post_res.json()

    # Query history
    hist_res = client.get("/api/predictions/history", params={"commodity": "potato", "limit": 10})
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert hist["count"] >= 1
    items = hist["history"]
    latest_item = items[0]
    assert latest_item["commodity"] == "potato"
    assert latest_item["market"] == "BENGALURU"
    assert latest_item["predicted_price"] == pred["predicted_price"]
    assert latest_item["estimated_gross_value"] == pred["estimated_gross_value"]


def test_analytics_endpoint_handles_vegetable_crops():
    for crop in ("potato", "tomato", "maize", "paddy"):
        res = client.get("/api/analytics", params={"commodity": crop, "days": 30})
        assert res.status_code == 200
        data = res.json()
        assert data["available"] is True
        assert data["commodity"] == crop
        assert len(data["historical"]) > 0
        assert data["latest"] is not None
        assert data["latest"]["price"] > 0
        assert data["trend"] in {"BULLISH", "BEARISH", "NEUTRAL"}
        assert len(data["market_comparison"]) > 0
