from apps.api import harvest_routes


def test_harvest_route_payload_includes_map_coordinates_and_route_geometry(monkeypatch):
    monkeypatch.setattr(
        harvest_routes,
        "market_rankings_payload",
        lambda *args, **kwargs: {
            "rankings": [
                {
                    "rank": 1,
                    "market_name": "Chikkamagaluru APMC",
                    "locations": ["Chikkamagaluru"],
                    "price": 240.0,
                    "unit": "INR_PER_KG",
                    "date": "2026-10-30",
                    "freshness_status": "recent",
                }
            ],
            "unit": "INR_PER_KG",
            "selected_series": "Arabica Parchment",
            "unit_note": None,
            "data_status": "test",
            "source": "test source",
        },
    )

    def fake_geocode(place):
        if "Sakleshpur" in place:
            return (12.9416, 75.7847)
        if "Chikkamagaluru" in place:
            return (13.3161, 75.7720)
        return None

    geometry = {
        "type": "LineString",
        "coordinates": [[75.7847, 12.9416], [75.80, 12.98], [75.7720, 13.3161]],
    }
    monkeypatch.setattr(harvest_routes, "_geocode", fake_geocode)
    monkeypatch.setattr(
        harvest_routes,
        "_road_route",
        lambda origin, destination: {
            "distance_km": 52.4,
            "duration_min": 74.0,
            "geometry": geometry,
        },
    )

    payload = harvest_routes.HarvestRouteRequest(
        commodity="coffee",
        origin="Sakleshpur, Hassan",
        quantity_kg=500,
        transport_cost_per_km=12,
        limit=1,
    )
    result = harvest_routes.harvest_routes_payload(None, payload)

    assert result["origin_coordinates"] == [12.9416, 75.7847]
    market = result["markets"][0]
    assert market["destination_coordinates"] == [13.3161, 75.7720]
    assert market["route_geometry"] == geometry
    assert market["distance_km"] == 52.4
    assert market["duration_min"] == 74


def test_osrm_route_helper_requests_and_returns_geojson_geometry(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "routes": [{
                    "distance": 12450,
                    "duration": 1800,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[75.7, 12.9], [75.8, 13.0]],
                    },
                }]
            }

    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(harvest_routes.httpx, "get", fake_get)
    route = harvest_routes._road_route((12.9, 75.7), (13.0, 75.8))

    assert captured["params"]["geometries"] == "geojson"
    assert captured["params"]["overview"] == "full"
    assert route["distance_km"] == 12.45
    assert route["duration_min"] == 30
    assert route["geometry"]["type"] == "LineString"
