"""Regression tests for Cold Storage individual coordinates, unique distances, and distinct Directions URLs."""

import pytest
from fastapi.testclient import TestClient

import apps.api.main as api_main
from apps.api.storage_service import StorageService


@pytest.fixture
def client():
    return TestClient(api_main.app)


def test_all_storage_facilities_have_unique_coordinates():
    """Verify that no two cold-storage facilities share the exact same coordinates."""
    service = StorageService()
    facilities_with_coords = [
        r for r in service.storages
        if r.get("latitude") is not None and r.get("longitude") is not None
    ]
    assert len(facilities_with_coords) >= 10, "Expected at least 10 facilities with coordinates"
    coord_pairs = [(r["latitude"], r["longitude"]) for r in facilities_with_coords]
    unique_pairs = set(coord_pairs)
    assert len(coord_pairs) == len(unique_pairs), (
        f"Found duplicate coordinates! Total: {len(coord_pairs)}, Unique: {len(unique_pairs)}"
    )


def test_madikeri_storage_facilities_have_distinct_distances_and_directions(client):
    """Test the exact user reported issue: Madikeri cold storages must not display identical 72.4 km distances."""
    resp = client.get("/api/cold-storage", params={"location": "Madikeri", "limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["match_type"] == "DISTRICT_NEARBY"
    facilities = data["facilities"]
    assert len(facilities) >= 5

    # 1. Distances must NOT all be identical (previously all were 72.4 km)
    distances = [f["distance_km"] for f in facilities]
    assert len(set(distances)) > 1, f"All facilities have identical distance_km: {distances}"

    # 2. Coordinates must all be distinct
    coords = [(f["latitude"], f["longitude"]) for f in facilities]
    assert len(coords) == len(set(coords)), f"Facilities share duplicate coordinates: {coords}"

    # 3. Directions URLs must be unique and point to individual coordinates
    directions = [f["directions_url"] for f in facilities]
    assert len(directions) == len(set(directions)), f"Facilities share duplicate directions URLs: {directions}"
    for f in facilities:
        assert f["directions_url"] is not None
        assert "destination=" in f["directions_url"]
        assert f"{f['latitude']},{f['longitude']}" in f["directions_url"]

    # 4. Each facility has a non-null, unique ID
    ids = [f["id"] for f in facilities]
    assert all(fid is not None and len(fid) > 0 for fid in ids)
    assert len(ids) == len(set(ids)), f"Duplicate facility IDs found: {ids}"


def test_changing_origin_location_recalculates_distances(client):
    """Verify that changing farmer location recalculates all distances and updates directions."""
    resp_madikeri = client.get("/api/cold-storage", params={"location": "Madikeri", "limit": 5}).json()
    resp_hassan = client.get("/api/cold-storage", params={"location": "Hassan", "limit": 5}).json()
    resp_sakleshpur = client.get("/api/cold-storage", params={"location": "Sakleshpur", "limit": 5}).json()

    madikeri_dists = [f["distance_km"] for f in resp_madikeri["facilities"]]
    hassan_dists = [f["distance_km"] for f in resp_hassan["facilities"]]
    sakleshpur_dists = [f["distance_km"] for f in resp_sakleshpur["facilities"]]

    # Distances must differ when origin changes
    assert madikeri_dists != hassan_dists
    assert hassan_dists != sakleshpur_dists
    assert madikeri_dists != sakleshpur_dists

    # Directions URLs must reflect the respective origin coordinates
    for f in resp_madikeri["facilities"]:
        assert "origin=" in f["directions_url"]
        assert "12.42149,75.7387543" in f["directions_url"]

    for f in resp_hassan["facilities"]:
        assert "origin=" in f["directions_url"]
        assert "13.0301852,76.1744968" in f["directions_url"]


def test_hassan_individual_facilities_plot_level_coordinates(client):
    """Verify that the 5 Hassan Growth Centre facilities have distinct plot-level coordinates."""
    resp = client.get("/api/cold-storage", params={"location": "Hassan", "limit": 10}).json()
    facilities = {f["name"]: f for f in resp["facilities"]}

    required_facilities = [
        "Jaswindera Cold Storage Pvt Ltd",
        "Satnam Agro Cold Storage",
        "Balaji Cold Storage",
        "J.P.G.A. Cold Storage Pvt Ltd",
        "Ganapati Cold Storage",
    ]
    for name in required_facilities:
        assert name in facilities, f"Missing facility {name}"
        f = facilities[name]
        assert f["latitude"] is not None and f["longitude"] is not None
        assert f["directions_url"] is not None
        assert f"{f['latitude']},{f['longitude']}" in f["directions_url"]

    # Compare pair-wise coordinates
    checked_coords = [
        (facilities[name]["latitude"], facilities[name]["longitude"])
        for name in required_facilities
    ]
    assert len(checked_coords) == len(set(checked_coords)), (
        f"Some of the 5 Hassan facilities share identical coordinates: {checked_coords}"
    )
