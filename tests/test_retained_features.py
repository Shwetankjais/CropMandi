from fastapi.testclient import TestClient

from apps.api.main import app


def test_harvest_route_health_is_available():
    response = TestClient(app).get("/api/harvest/health")
    assert response.status_code == 200
    assert response.json()["feature"] == "harvest-route"


def test_four_supplied_crop_models_are_registered():
    response = TestClient(app).get("/api/ai-crops")
    assert response.status_code == 200
    assert {item["crop"] for item in response.json()["models"]} == {
        "tomato", "maize", "paddy", "potato"
    }


def test_msg91_alert_api_is_not_registered():
    response = TestClient(app).get("/api/alerts/config")
    assert response.status_code == 404
