"""Market comparison and route planning helpers for Harvest Route.

Market prices come from the existing CropMandi market-ranking providers. For
route distances this prototype geocodes town centres with Nominatim and asks the
public OSRM demo server for driving routes. Town-centre routes are indicative,
not verified routes to an individual trader's gate.
"""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.market_rankings import market_rankings_payload
from apps.api.services import parse_commodity

router = APIRouter(prefix="/api/harvest", tags=["harvest-route"])


class HarvestRouteRequest(BaseModel):
    commodity: str = Field(pattern="^(coffee|pepper|rice)$")
    origin: str = Field(min_length=2, max_length=160)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    series: str | None = Field(default=None, max_length=250)
    quantity_kg: float = Field(gt=0, le=1000000)
    transport_cost_per_km: float = Field(default=12.0, ge=0, le=10000)
    limit: int = Field(default=5, ge=1, le=5)


@lru_cache(maxsize=256)
def _geocode(place: str) -> tuple[float, float] | None:
    """Nominatim lookup; cache results to avoid repeated public-service calls."""
    query = place.strip()
    if not query:
        return None
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "in"},
            headers={"User-Agent": "CropMandiAI-HarvestRoute/1.0 (prototype)"},
            timeout=12.0,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            return None
        return float(results[0]["lat"]), float(results[0]["lon"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


def _road_route(origin: tuple[float, float], destination: tuple[float, float]) -> dict[str, Any] | None:
    """Return route metrics and GeoJSON geometry from OSRM.

    OSRM coordinates are longitude,latitude; the public API response is
    converted to Leaflet-ready GeoJSON for the Harvest Route map.
    """
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    )
    try:
        response = httpx.get(
            url,
            params={"overview": "full", "geometries": "geojson", "steps": "false"},
            timeout=20.0,
        )
        response.raise_for_status()
        routes = response.json().get("routes") or []
        if not routes:
            return None
        selected = routes[0]
        geometry = selected.get("geometry")
        if not isinstance(geometry, dict) or not isinstance(geometry.get("coordinates"), list):
            geometry = None
        return {
            "distance_km": float(selected["distance"]) / 1000.0,
            "duration_min": float(selected["duration"]) / 60.0,
            "geometry": geometry,
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


def _price_per_kg(price: float, unit: str | None) -> float | None:
    label = (unit or "").lower().replace(" ", "")
    if not label:
        return None
    if "50kg" in label or "/50kg" in label:
        return price / 50.0
    if "quintal" in label or "100kg" in label or "/qtl" in label:
        return price / 100.0
    if "tonne" in label or "metricton" in label:
        return price / 1000.0
    if "perkg" in label or "/kg" in label or label.endswith("kg"):
        return price
    return None


def harvest_routes_payload(session: Session, payload: HarvestRouteRequest) -> dict[str, Any]:
    rankings_payload = market_rankings_payload(
        session,
        parse_commodity(payload.commodity),
        series=payload.series,
        limit=payload.limit,
    )
    rankings = rankings_payload.get("rankings") or []
    if not rankings:
        raise HTTPException(status_code=404, detail="No market ranking data is available for this crop/variety yet.")

    origin_coords = None
    if payload.latitude is not None and payload.longitude is not None:
        origin_coords = (payload.latitude, payload.longitude)
    else:
        origin_coords = _geocode(f"{payload.origin}, India")
    if origin_coords is None:
        raise HTTPException(status_code=422, detail="Could not locate the farm location. Enter a clearer village/town and district, or use the GPS button.")

    price_unit = rankings_payload.get("unit")
    output = []
    for index, market in enumerate(rankings):
        places = market.get("locations") or []
        town = str(places[0]) if places else str(market.get("market_name") or "").strip()
        destination_query = f"{town}, Karnataka, India" if town else f"{market.get('market_name')}, India"
        # Nominatim's public service asks clients to avoid rapid repeated queries.
        destination_coords = _geocode(destination_query)
        if destination_coords is None:
            output.append({
                "rank": market.get("rank", index + 1),
                "market_name": market.get("market_name"),
                "town": town,
                "price": market.get("price"),
                "unit": price_unit or market.get("unit"),
                "distance_km": None,
                "duration_min": None,
                "gross_estimate_inr": None,
                "transport_estimate_inr": None,
                "net_estimate_inr": None,
                "destination_coordinates": None,
                "route_geometry": None,
                "route_url": "https://www.google.com/maps/dir/?" + urlencode({"api": "1", "origin": payload.origin, "destination": destination_query, "travelmode": "driving"}),
                "route_status": "destination_not_geocoded",
            })
            continue

        route = _road_route(origin_coords, destination_coords)
        price = float(market.get("price") or 0.0)
        per_kg = _price_per_kg(price, price_unit or market.get("unit"))
        distance = route["distance_km"] if route else None
        duration = route["duration_min"] if route else None
        gross = round(per_kg * payload.quantity_kg, 2) if per_kg is not None else None
        transport = round(distance * payload.transport_cost_per_km, 2) if distance is not None else None
        net = round(gross - transport, 2) if gross is not None and transport is not None else None
        output.append({
            "rank": market.get("rank", index + 1),
            "market_name": market.get("market_name"),
            "town": town,
            "price": price,
            "unit": price_unit or market.get("unit"),
            "price_date": market.get("date"),
            "price_freshness": market.get("freshness_status"),
            "distance_km": round(distance, 1) if distance is not None else None,
            "duration_min": round(duration) if duration is not None else None,
            "gross_estimate_inr": gross,
            "transport_estimate_inr": transport,
            "net_estimate_inr": net,
            "destination_coordinates": [destination_coords[0], destination_coords[1]],
            "route_geometry": route.get("geometry") if route else None,
            "route_url": "https://www.google.com/maps/dir/?" + urlencode({"api": "1", "origin": payload.origin, "destination": destination_query, "travelmode": "driving"}),
            "route_status": "road_route_available" if route else "route_unavailable",
        })
        # Keep a small gap between public Nominatim lookups. Cached locations do not wait.
        if index < len(rankings) - 1:
            time.sleep(1.0)

    comparable = any(item.get("net_estimate_inr") is not None for item in output)
    if comparable:
        output.sort(key=lambda item: (item.get("net_estimate_inr") is None, -(item.get("net_estimate_inr") or 0)))
        for item in output:
            item["recommendation_basis"] = "Estimated sale proceeds minus estimated road transport cost"
    else:
        output.sort(key=lambda item: (item.get("price") is None, -(item.get("price") or 0)))
        for item in output:
            item["recommendation_basis"] = "Reported market price only; source unit is missing or route distance is unavailable"

    for index, item in enumerate(output, start=1):
        item["recommendation_order"] = index

    return {
        "commodity": payload.commodity,
        "selected_series": rankings_payload.get("selected_series"),
        "origin": payload.origin,
        "origin_coordinates": [origin_coords[0], origin_coords[1]],
        "quantity_kg": payload.quantity_kg,
        "transport_cost_per_km": payload.transport_cost_per_km,
        "price_unit": price_unit,
        "unit_note": rankings_payload.get("unit_note"),
        "markets": output,
        "ranking_method": "Highest estimated net proceeds when price units and road distances are available; otherwise reported market price only.",
        "data_status": rankings_payload.get("data_status"),
        "source": rankings_payload.get("source"),
        "limitations": [
            "Route endpoints use geocoded town centres, not verified individual mandi gates.",
            "OSRM public demo routing and OpenStreetMap geocoding are best-effort services without a production SLA.",
            "A net estimate is shown only when the source price unit can safely be converted to INR per kg and a road distance is available.",
            "Actual trader bids, commissions, loading, taxes, tolls, return-trip costs and spoilage are not included.",
        ],
    }


@router.get("/health")
def harvest_route_health() -> dict[str, str]:
    return {"feature": "harvest-route", "status": "available", "routing": "OSRM public demo; no API key required"}
