"""
CropMandi AI — Phase 2 End-to-End Workflow & Multi-Module Integration Tests.

Validates complete real-world user journeys across modules:
1. Farmer Crop Management (Add, List, Update, Summary Metrics, Delete).
2. Mandi Price AI multi-crop forecasting.
3. HarvestRoute quantity-aware vehicle optimization & net profit ranking.
4. Cold Storage multi-facility distance calculation with OSRM & GPS mapping.
5. Real-time Weather intelligence.
6. Market Analytics multi-crop data.
"""

from fastapi.testclient import TestClient
import pytest
from apps.api.main import app

client = TestClient(app)


def test_end_to_end_farmer_crop_lifecycle():
    """Test full CRUD lifecycle of a crop in farmer's inventory."""
    # 1. Fetch initial inventory metadata and crops
    meta_resp = client.get("/api/farmer/crops/metadata")
    assert meta_resp.status_code == 200
    meta_data = meta_resp.json()
    assert "commodities" in meta_data
    assert len(meta_data["commodities"]) == 7

    # 2. Add new test crop (Potato)
    new_crop_payload = {
        "commodity": "potato",
        "variety": "Jyoti",
        "quantity": 150.0,
        "unit": "quintal",
        "location": "Hassan",
    }
    create_resp = client.post("/api/farmer/crops", json=new_crop_payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["crop"]["commodity"] == "potato"
    assert created["crop"]["quantity"] == 150.0
    crop_id = created["crop"]["id"]

    # 3. Verify crop appears in list and portfolio metrics
    list_resp = client.get("/api/farmer/crops")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["count"] >= 1
    assert any(c["id"] == crop_id for c in list_data["crops"])

    # 4. Update the crop (change quantity to 200 quintals)
    update_resp = client.put(
        f"/api/farmer/crops/{crop_id}",
        json={"quantity": 200.0},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()["crop"]
    assert updated["quantity"] == 200.0

    # 5. Delete the test crop and confirm deletion
    del_resp = client.delete(f"/api/farmer/crops/{crop_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # Confirm not in list
    list_after = client.get("/api/farmer/crops").json()
    assert not any(c["id"] == crop_id for c in list_after["crops"])


def test_end_to_end_mandi_forecast_to_harvestroute_workflow():
    """Farmer gets ML price forecast, then optimizes transportation and routes."""
    # Step A: Get price prediction for Tomato
    pred_resp = client.get("/api/predictions/next?commodity=tomato")
    assert pred_resp.status_code == 200
    pred = pred_resp.json()
    assert pred["available"] is True
    assert pred["next_session_estimate"] > 0

    # Step B: Get available transport vehicles
    vehicles_resp = client.get("/api/harvest/vehicles")
    assert vehicles_resp.status_code == 200
    vehicles = vehicles_resp.json()["vehicles"]
    assert len(vehicles) >= 6

    # Select medium truck
    medium_truck = next(v for v in vehicles if "medium" in v["id"].lower() or "1109" in v.get("model", ""))
    assert medium_truck["max_payload_kg"] >= 4000

    # Step C: Plan harvest route for 5,000 kg from Sakleshpur
    route_resp = client.post(
        "/api/harvest/routes",
        json={
            "commodity": "coffee",
            "series": "Arabica Parchment",
            "quantity_kg": 5000,
            "latitude": 12.91,
            "longitude": 75.78,
            "origin": "Sakleshpur, Hassan",
            "vehicle_id": medium_truck["id"],
            "ownership": "hired",
        },
    )
    assert route_resp.status_code == 200
    route_data = route_resp.json()
    assert len(route_data["markets"]) >= 1
    top_route = route_data["markets"][0]
    assert top_route["net_estimate_inr"] > 0
    assert top_route["rank"] == 1
    assert "profit_breakdown" in top_route


def test_end_to_end_cold_storage_lookup_and_navigation():
    """Verify cold storage facility lookup returns distinct coordinates and directions."""
    resp = client.get("/api/cold-storage?location=Madikeri&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    facilities = data.get("facilities", [])
    assert len(facilities) > 0

    # Verify each facility has coordinates & directions URL
    coords = set()
    for f in facilities:
        assert f["latitude"] is not None
        assert f["longitude"] is not None
        assert f["directions_url"] is not None
        assert "google.com/maps/dir" in f["directions_url"]
        coords.add((f["latitude"], f["longitude"]))

    # Multiple facilities must NOT all have identical coordinates
    assert len(coords) >= 3


def test_end_to_end_weather_intelligence():
    """Verify live weather service responds for major agricultural hubs."""
    resp = client.get("/api/weather?location=Sakleshpur")
    assert resp.status_code in [200, 503]
    data = resp.json()
    if resp.status_code == 200:
        assert "temperature_c" in data
        assert "description" in data
        assert "humidity_percent" in data
    else:
        assert data.get("error") == "weather_unavailable"


def test_end_to_end_market_analytics():
    """Verify analytics response for both plantation and vegetable commodities."""
    for commodity in ["coffee", "pepper", "tomato", "potato"]:
        resp = client.get(f"/api/analytics?commodity={commodity}&days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["commodity"] == commodity
        assert "historical" in data
        assert "trend" in data
