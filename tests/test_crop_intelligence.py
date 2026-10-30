from __future__ import annotations

import math

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.location_services import MapplsClient, haversine_km
from ml.crop_prediction_service import MODEL_CONFIG, load_model

client = TestClient(app)


def test_all_four_supplied_models_load_with_expected_feature_count():
    for crop, config in MODEL_CONFIG.items():
        model = load_model(crop)
        assert model.n_features_in_ == len(config["features"])
        assert callable(model.predict)


def test_real_uploaded_history_can_drive_all_four_models():
    for crop in ("tomato", "maize", "paddy", "potato"):
        options_response = client.get("/api/crops/options", params={"crop": crop})
        assert options_response.status_code == 200
        payload = options_response.json()
        market = next(item for item in payload["markets"] if item["series_options"])
        series = next(item for item in market["series_options"] if item["prediction_ready"])
        prediction = client.post("/api/crops/predict", json={
            "crop": crop,
            "market_name": market["market_name"],
            "district": market["district"],
            "variety": series["variety"],
            "grade": series["grade"],
        })
        assert prediction.status_code == 200, prediction.text
        result = prediction.json()
        assert result["prediction_kind"] == config_kind(crop)
        assert math.isfinite(result["raw_model_output"])
        assert result["history_observations_used"] >= 8
        assert result["model_accuracy_status"] == "NOT_VALIDATED_AGAINST_HELD_OUT_ACTUALS"


def config_kind(crop: str) -> str:
    return MODEL_CONFIG[crop]["kind"]


def test_crop_rankings_return_real_uploaded_observations():
    for crop in MODEL_CONFIG:
        response = client.get("/api/crops/rankings", params={"crop": crop, "limit": 5})
        assert response.status_code == 200
        payload = response.json()
        assert payload["rankings"]
        assert payload["rankings"][0]["price"] > 0
        assert payload["data_status"] == "USER_SUPPLIED_AGMARKNET_EXPORT_UNVERIFIED"


def test_mappls_unconfigured_matrix_is_explicitly_straight_line_only():
    client = MapplsClient(rest_key="")
    result = client.distance_matrix(
        {"latitude": 12.0, "longitude": 76.0},
        [{"name": "Example Mandi", "latitude": 12.1, "longitude": 76.1}],
    )
    assert result["provider"].startswith("Haversine")
    assert result["is_road_distance"] is False
    assert result["results"][0]["distance_type"] == "STRAIGHT_LINE_APPROXIMATION"
    assert result["results"][0]["duration_minutes"] is None


def test_haversine_returns_zero_for_same_point():
    assert haversine_km(12.0, 76.0, 12.0, 76.0) == 0.0


def test_map_config_never_returns_server_rest_secret():
    response = client.get("/api/location/map-config")
    assert response.status_code == 200
    assert "rest_api_key" not in response.json()
    assert "rest_key" not in response.json()


def test_mappls_matrix_parses_mocked_provider_response_and_coordinate_order():
    import httpx

    seen = {}

    def handler(request):
        seen["url"] = request.url
        return httpx.Response(200, json={
            "results": {
                "code": "Ok",
                "distances": [[0, 5000]],
                "durations": [[0, 600]],
            }
        })

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        service = MapplsClient(rest_key="test-rest-key", client=http_client)
        result = service.distance_matrix(
            {"latitude": 12.0, "longitude": 76.0},
            [{"name": "Test Mandi", "latitude": 12.2, "longitude": 76.3}],
            profile="driving",
        )

    assert result["provider"] == "Mappls"
    assert result["is_road_distance"] is True
    assert result["results"][0]["distance_km"] == 5.0
    assert result["results"][0]["duration_minutes"] == 10.0
    assert "/driving/76.0,12.0;76.3,12.2" in seen["url"].path
    assert seen["url"].params["region"] == "ind"
    assert seen["url"].params["rtype"] == "0"


def test_mandi_coordinate_confirmation_requires_server_token(monkeypatch):
    monkeypatch.delenv("MANDI_COORDINATE_ADMIN_TOKEN", raising=False)
    disabled = client.post("/api/mandis/999999/confirm", json={"latitude": 12.0, "longitude": 76.0})
    assert disabled.status_code == 503

    monkeypatch.setenv("MANDI_COORDINATE_ADMIN_TOKEN", "test-admin-secret")
    forbidden = client.post("/api/mandis/999999/confirm", json={"latitude": 12.0, "longitude": 76.0})
    assert forbidden.status_code == 403
    missing_market = client.post(
        "/api/mandis/999999/confirm",
        json={"latitude": 12.0, "longitude": 76.0},
        headers={"X-Mandi-Admin-Token": "test-admin-secret"},
    )
    assert missing_market.status_code == 404


def test_farmer_location_capture_is_not_persisted_when_mappls_is_unconfigured():
    response = client.post("/api/location/capture", json={
        "latitude": 12.0,
        "longitude": 76.0,
        "accuracy_m": 12,
        "purpose": "farm",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["stored"] is False
    assert payload["latitude"] == 12.0
    assert payload["reverse_geocode"]["configured"] is False
