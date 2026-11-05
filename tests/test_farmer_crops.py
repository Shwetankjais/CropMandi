"""Tests for Farmer Crops management supporting all 7 commodities."""

from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from apps.api.main import app
from apps.api.farmer_crops import SUPPORTED_COMMODITIES, COMMODITY_IMAGES, normalize_commodity_code
from cropmandi.db.session import make_session_factory
from cropmandi.db.models import FarmerCrop


@pytest.fixture
def client():
    return TestClient(app)


def test_crop_images_exist_locally():
    """Verify that all 7 photographic crop assets exist in frontend/assets/crops/."""
    root = Path(__file__).resolve().parents[1]
    assets_dir = root / "frontend" / "assets" / "crops"
    assert assets_dir.exists(), "frontend/assets/crops directory must exist"

    expected_files = [
        "coffee.jpg",
        "black-pepper.jpg",
        "cardamom.jpg",
        "paddy.jpg",
        "tomato.jpg",
        "potato.jpg",
        "maize.jpg",
    ]
    for filename in expected_files:
        p = assets_dir / filename
        assert p.exists(), f"Image file {filename} must exist"
        assert p.stat().st_size > 10000, f"Image file {filename} must not be empty or truncated"


def test_farmer_crops_metadata(client):
    """Verify that metadata endpoint returns all 7 commodities and proper capabilities."""
    res = client.get("/api/farmer/crops/metadata")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["commodities"]) == 7

    codes = {c["code"] for c in data["commodities"]}
    expected_codes = {"coffee", "pepper", "cardamom", "paddy", "tomato", "potato", "maize"}
    assert codes == expected_codes

    # Check ML forecasting support flag
    for c in data["commodities"]:
        if c["code"] in {"paddy", "tomato", "potato", "maize"}:
            assert c["has_ml_forecasting"] is True, f"{c['code']} must have ML forecasting"
        else:
            assert c["has_ml_forecasting"] is False, f"{c['code']} should not have ML forecasting"


def test_normalize_commodity_code():
    """Verify commodity alias normalization."""
    assert normalize_commodity_code("rice") == "paddy"
    assert normalize_commodity_code("RICE") == "paddy"
    assert normalize_commodity_code("black pepper") == "pepper"
    assert normalize_commodity_code("BLACK_PEPPER") == "pepper"
    assert normalize_commodity_code("corn") == "maize"
    assert normalize_commodity_code("tomato") == "tomato"


def test_farmer_crops_crud_cycle(client):
    """Test full CRUD lifecycle for farmer crops across commodities."""
    # 1. List
    list_res = client.get("/api/farmer/crops")
    assert list_res.status_code == 200
    initial_crops = list_res.json()["crops"]
    assert len(initial_crops) >= 3

    # 2. Create Paddy crop
    paddy_payload = {
        "commodity": "paddy",
        "variety": "Sona Masuri",
        "quantity": 75.0,
        "unit": "quintal",
        "location": "Davanagere",
    }
    create_res = client.post("/api/farmer/crops", json=paddy_payload)
    assert create_res.status_code == 201
    created_paddy = create_res.json()["crop"]
    paddy_id = created_paddy["id"]
    assert created_paddy["commodity"] == "paddy"
    assert created_paddy["variety"] == "Sona Masuri"
    assert created_paddy["quantity"] == 75.0

    # 3. Create Tomato crop with alias normalization ("tomato")
    tomato_payload = {
        "commodity": "tomato",
        "variety": "Hybrid Tomato",
        "quantity": 120.0,
        "unit": "crate (25kg)",
        "location": "Kolar",
    }
    tomato_res = client.post("/api/farmer/crops", json=tomato_payload)
    assert tomato_res.status_code == 201
    created_tomato = tomato_res.json()["crop"]
    tomato_id = created_tomato["id"]
    assert created_tomato["commodity"] == "tomato"

    # 4. Update crop
    update_res = client.put(f"/api/farmer/crops/{paddy_id}", json={"quantity": 85.5, "location": "Shivamogga"})
    assert update_res.status_code == 200
    updated_paddy = update_res.json()["crop"]
    assert updated_paddy["quantity"] == 85.5
    assert updated_paddy["location"] == "Shivamogga"

    # 5. Delete crops to keep database clean
    del_res1 = client.delete(f"/api/farmer/crops/{paddy_id}")
    assert del_res1.status_code == 200
    del_res2 = client.delete(f"/api/farmer/crops/{tomato_id}")
    assert del_res2.status_code == 200


def test_farmer_crops_validation_errors(client):
    """Verify input validation rules."""
    # Invalid commodity
    res_bad_comm = client.post("/api/farmer/crops", json={
        "commodity": "pineapples",
        "variety": "Queen",
        "quantity": 10,
        "location": "Sirsi",
    })
    assert res_bad_comm.status_code == 400

    # Invalid negative quantity
    res_bad_qty = client.post("/api/farmer/crops", json={
        "commodity": "potato",
        "variety": "Jyoti",
        "quantity": -5,
        "location": "Hassan",
    })
    assert res_bad_qty.status_code == 400  # RequestValidationError handled as 400

    # Update non-existent crop
    res_404 = client.put("/api/farmer/crops/999999", json={"quantity": 10})
    assert res_404.status_code == 404

    # Delete non-existent crop
    del_404 = client.delete("/api/farmer/crops/999999")
    assert del_404.status_code == 404


def test_add_all_seven_commodities(client):
    """Verify that all 7 commodities can be added to farmer inventory and retrieved."""
    test_specs = [
        {"commodity": "coffee", "variety": "Robusta Parchment", "quantity": 15.0, "unit": "quintal", "location": "Mudigere"},
        {"commodity": "pepper", "variety": "Sirsi", "quantity": 10.0, "unit": "quintal", "location": "Sirsi"},
        {"commodity": "cardamom", "variety": "Small Cardamom (Green)", "quantity": 25.0, "unit": "kg", "location": "Madikeri"},
        {"commodity": "paddy", "variety": "Basmati", "quantity": 40.0, "unit": "quintal", "location": "Mandya"},
        {"commodity": "tomato", "variety": "Roma", "quantity": 20.0, "unit": "quintal", "location": "Bengaluru"},
        {"commodity": "potato", "variety": "Kufri Chandramukhi", "quantity": 30.0, "unit": "quintal", "location": "Hassan"},
        {"commodity": "maize", "variety": "White Maize", "quantity": 50.0, "unit": "quintal", "location": "Haveri"},
    ]

    created_ids = []
    try:
        for spec in test_specs:
            res = client.post("/api/farmer/crops", json=spec)
            assert res.status_code == 201, f"Failed to add {spec['commodity']}: {res.text}"
            data = res.json()
            assert data["success"] is True
            assert data["crop"]["commodity"] == spec["commodity"]
            created_ids.append(data["crop"]["id"])

        # Verify all are present in listing
        list_res = client.get("/api/farmer/crops")
        assert list_res.status_code == 200
        all_crops = list_res.json()["crops"]
        commodities_in_list = {c["commodity"] for c in all_crops}
        for spec in test_specs:
            assert spec["commodity"] in commodities_in_list
    finally:
        # Cleanup
        for cid in created_ids:
            client.delete(f"/api/farmer/crops/{cid}")

