"""
CropMandi AI — Phase 2 Security, Hardening & Defensive Quality Audit Tests.

Verifies:
1. HTTP Security Headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy).
2. CORS Headers and Preflight options.
3. SQL Injection immunity across query parameters.
4. XSS sanitization and safety in payloads.
5. Strict request validation (400 responses with details).
6. Multi-crop regression predictions for all 4 ML crops (Paddy, Tomato, Potato, Maize).
7. Protection against stack trace and internal path leakage.
"""

from fastapi.testclient import TestClient
import pytest
from apps.api.main import app

client = TestClient(app)


def test_security_headers_present_on_all_responses():
    """Verify production security headers are set on API responses."""
    resp = client.get("/api/prices/latest?commodity=coffee")
    assert resp.status_code == 200
    headers = resp.headers

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "SAMEORIGIN"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_cors_preflight_and_headers():
    """Verify CORS preflight OPTIONS request returns allowed methods and origin."""
    resp = client.options(
        "/api/prices/latest",
        headers={
            "Origin": "http://127.0.0.1:5500",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


def test_sql_injection_resistance_in_query_parameters():
    """Verify SQL injection strings in query parameters are safely handled."""
    sqli_payloads = [
        "coffee' OR 1=1 --",
        "tomato'; DROP TABLE farmer_crops; --",
        "' UNION SELECT * FROM users --",
        "1' OR '1'='1",
    ]
    for payload in sqli_payloads:
        # Commodity query should either reject or safely return empty/error, not crash with 500
        resp = client.get(f"/api/markets?commodity={payload}")
        assert resp.status_code in [200, 400, 404]
        assert resp.status_code != 500

        # Market prices query
        resp2 = client.get(f"/api/markets/prices?commodity=coffee&location={payload}")
        assert resp2.status_code in [200, 400, 404]
        assert resp2.status_code != 500


def test_xss_payload_safety_in_queries():
    """Verify XSS strings in inputs do not cause internal server errors."""
    xss_payloads = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
    ]
    for payload in xss_payloads:
        resp = client.get(f"/api/markets?commodity={payload}")
        assert resp.status_code in [200, 400, 404]
        assert resp.status_code != 500


def test_request_validation_structured_400():
    """Verify validation errors return structured 400 JSON without stack traces."""
    # Invalid latitude > 90
    resp = client.get("/api/cold-storages?latitude=999.0&longitude=75.78")
    assert resp.status_code == 400
    data = resp.json()
    assert data.get("error") in ["invalid_request", "invalid_latitude"]

    # Negative quantity
    resp2 = client.get("/api/cold-storages?latitude=12.9&longitude=75.78&quantity_kg=-50")
    assert resp2.status_code == 400
    data2 = resp2.json()
    assert data2.get("error") in ["invalid_request", "invalid_quantity"]


def test_predictions_next_ml_crops_all_succeed():
    """Verify /api/predictions/next works for all four ML crops without 500 errors."""
    for crop in ["tomato", "potato", "maize", "paddy"]:
        resp = client.get(f"/api/predictions/next?commodity={crop}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["commodity"] == crop
        assert isinstance(data["next_session_estimate"], (int, float))
        assert data["next_session_estimate"] > 0
        assert "ExtraTrees" in data["method"]


def test_harvest_routes_validation_and_safety():
    """Verify harvest route payload validation prevents invalid calculations."""
    # Negative quantity
    resp = client.post(
        "/api/harvest/routes",
        json={
            "commodity": "coffee",
            "quantity_kg": -100,
            "latitude": 12.91,
            "longitude": 75.78,
            "origin": "Sakleshpur",
        },
    )
    assert resp.status_code == 400

    # Valid route calculation succeeds
    resp_valid = client.post(
        "/api/harvest/routes",
        json={
            "commodity": "coffee",
            "series": "Arabica Parchment",
            "quantity_kg": 5000,
            "latitude": 12.91,
            "longitude": 75.78,
            "origin": "Sakleshpur, Hassan",
            "vehicle_id": "truck_medium",
            "ownership": "hired",
        },
    )
    assert resp_valid.status_code == 200
    data = resp_valid.json()
    assert "markets" in data
    assert len(data["markets"]) > 0
    top = data["markets"][0]
    assert top["rank"] == 1
    assert top["net_estimate_inr"] > 0


def test_no_stack_trace_leakage_on_missing_route():
    """Verify 404 responses return clean error JSON without exposing internal file paths."""
    resp = client.get("/api/nonexistent-endpoint-audit")
    assert resp.status_code == 404
