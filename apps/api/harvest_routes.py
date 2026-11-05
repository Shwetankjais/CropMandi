"""Market comparison and route planning helpers for Harvest Route.

Enhanced (v2):
  - Quantity-aware, vehicle-specific transport cost engine
  - Smart mandi ranking by net realization (not just distance)
  - Vehicle auto-recommendation mode
  - Support for coffee, pepper, rice, tomato, maize, paddy, potato

Market prices come from the existing CropMandi market-ranking providers. For
route distances this prototype geocodes town centres with Nominatim and asks the
public OSRM demo server for driving routes. Town-centre routes are indicative,
not verified routes to an individual trader's gate.
"""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Literal, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from apps.api.market_rankings import market_rankings_payload
from apps.api.services import parse_commodity
from apps.api.vehicle_catalogue import (
    get_all_vehicles,
    get_diesel_price,
    get_petrol_price,
    get_vehicle_by_id,
)
from apps.api.vehicle_service import recommend_vehicle, validate_payload
from apps.api.mandi_optimizer import rank_markets

router = APIRouter(prefix="/api/harvest", tags=["harvest-route"])

# Supported commodity pattern (extended from v1)
_COMMODITY_PATTERN = "^(coffee|pepper|rice|tomato|maize|paddy|potato)$"


class HarvestRouteRequest(BaseModel):
    """Request schema for the quantity-aware HarvestRoute endpoint (v2).

    ``transport_cost_per_km`` is kept for backward compatibility; when
    provided without ``vehicle_id`` it is used as an override flat rate.
    """
    commodity: str = Field(pattern=_COMMODITY_PATTERN)
    origin: str = Field(min_length=2, max_length=160)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    series: str | None = Field(default=None, max_length=250)
    quantity_kg: float = Field(gt=0, le=1000000)

    # Vehicle selection
    vehicle_mode: Literal["auto", "manual"] = Field(default="auto")
    vehicle_id: str | None = Field(default=None)
    ownership: Literal["owned", "hired"] = Field(default="hired")

    # Legacy flat-rate field (backward compat)
    transport_cost_per_km: float | None = Field(default=None, ge=0, le=10000)

    limit: int = Field(default=5, ge=1, le=5)

    @model_validator(mode="after")
    def _validate_manual_vehicle(self) -> "HarvestRouteRequest":
        if self.vehicle_mode == "manual" and not self.vehicle_id:
            # Fall back to auto if manual but no vehicle given
            self.vehicle_mode = "auto"
        return self


# ---------------------------------------------------------------------------
# Curated Coordinates for Karnataka Mandis & Plantation Centers
# ---------------------------------------------------------------------------

import json
import re

KNOWN_LOCATIONS: dict[str, tuple[float, float]] = {
    # Coffee & Spice plantation hubs
    "sakleshpur": (12.9434, 75.7862),
    "mudigere": (13.1333, 75.6419),
    "kushalnagar": (12.4586, 75.9614),
    "kushalnagara": (12.4586, 75.9614),
    "gendehalli": (13.1840, 75.7578),
    "makkandur": (12.4833, 75.7333),
    "hassan": (13.0033, 76.1004),
    "chikkamagaluru": (13.3161, 75.7720),
    "chikmagalur": (13.3161, 75.7720),
    "madikeri": (12.4244, 75.7382),
    "somwarpet": (12.5986, 75.8672),
    "virajpet": (12.2034, 75.8037),
    "gonikoppal": (12.1833, 75.9333),
    "gonikoppa": (12.1833, 75.9333),
    "suntikoppa": (12.4833, 75.8333),
    "shanivarasanthe": (12.7500, 75.9167),
    "siddapur": (12.3000, 75.8833),
    "balehonnur": (13.3500, 75.4667),
    "aldur": (13.2500, 75.6333),
    "kalasa": (13.2333, 75.3667),
    "sringeri": (13.4167, 75.2500),
    "koppa": (13.5333, 75.3667),
    "belur": (13.1633, 75.8647),
    "ballupete": (12.9167, 75.8833),
    "balupet": (12.9167, 75.8833),
    "hanbalu": (12.9833, 75.7167),
    "kodlipete": (12.8000, 75.8667),
    "pattadur": (13.1000, 75.6000),
    "theni": (10.0104, 77.4768),
    "bodinayakanur": (10.0104, 77.3496),
    "wayanad": (11.6050, 76.0830),
    "kalpetta": (11.6050, 76.0830),
    "sulthanbathery": (11.6622, 76.2570),
    "mananthavady": (11.8028, 76.0033),
    "cochin": (9.9312, 76.2673),
    "kochi": (9.9312, 76.2673),
    # APMC & Major Agricultural Mandis in Karnataka
    "kolar": (13.1367, 78.1292),
    "nanjangud": (12.1197, 76.6808),
    "haveri": (14.7954, 75.3991),
    "sira": (13.7447, 76.9067),
    "kottur": (14.8239, 76.2208),
    "shimoga": (13.9299, 75.5681),
    "shivamogga": (13.9299, 75.5681),
    "davangere": (14.4644, 75.9218),
    "davanagere": (14.4644, 75.9218),
    "gangavathi": (15.4333, 76.5333),
    "mysuru": (12.2958, 76.6394),
    "mysore": (12.2958, 76.6394),
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "sirsi": (14.6195, 74.8354),
    "sagar": (14.1670, 75.0333),
    "puttur": (12.7661, 75.2044),
    "mangalore": (12.9141, 74.8560),
    "mangaluru": (12.9141, 74.8560),
    "karkala": (13.2167, 74.9967),
    "byadgi": (14.6800, 75.4800),
    "arsikere": (13.3134, 76.2570),
    "kadur": (13.5500, 76.0167),
    "tarikere": (13.7167, 75.8167),
    "ballari": (15.1394, 76.9214),
    "bellary": (15.1394, 76.9214),
    "raichur": (16.2076, 77.3463),
    "hubli": (15.3647, 75.1240),
    "hubballi": (15.3647, 75.1240),
    "dharwad": (15.4589, 75.0078),
    "belagavi": (15.8497, 74.4977),
    "belgaum": (15.8497, 74.4977),
    "bagalkot": (16.1691, 75.6615),
    "vijayapura": (16.8302, 75.7100),
    "bijapur": (16.8302, 75.7100),
    "chitradurga": (14.2251, 76.3980),
    "tumakuru": (13.3379, 77.1173),
    "tumkur": (13.3379, 77.1173),
    "udupi": (13.3409, 74.7421),
    "ramanagara": (12.7150, 77.2810),
    "chintamani": (13.4000, 78.0667),
    "srinivaspur": (13.3333, 78.2167),
    "malur": (13.0042, 77.9406),
    "doddaballapur": (13.2929, 77.5434),
    "chikkaballapur": (13.4355, 77.7315),
    "holenarasipura": (12.7889, 76.2417),
    "channarayapatna": (12.9056, 76.3889),
    "crpatna": (12.9056, 76.3889),
    "arakalgud": (12.7667, 76.0500),
    "annigeri": (15.4333, 75.4333),
    "athani": (16.7333, 75.0667),
    "badami": (15.9167, 75.6833),
    "bagepalli": (13.7833, 77.7833),
    "bailhongal": (15.8167, 74.8667),
    "bangarpet": (12.9833, 78.2000),
    "basavakalyana": (17.8667, 76.9500),
    "bhadravathi": (13.8400, 75.7000),
    "bidar": (17.9104, 77.5199),
    "bilagi": (16.3500, 75.6167),
    "challakere": (14.3167, 76.6500),
    "channagiri": (14.1167, 75.9333),
    "channapatna": (12.6500, 77.2000),
    "gokak": (16.1667, 74.8333),
    "hospet": (15.2689, 76.3909),
    "hosapete": (15.2689, 76.3909),
    "jamkhandi": (16.5000, 75.3000),
    "koppal": (15.3500, 76.1500),
    "lingasugur": (16.1667, 76.5167),
    "mandya": (12.5200, 76.9000),
    "ranebennur": (14.6239, 75.6208),
    "sindhanur": (15.7667, 76.7667),
    "tiptur": (13.2556, 76.4789),
    "yadgir": (16.7700, 77.1400),
}


def _resolve_known(place: str) -> tuple[float, float] | None:
    if not place or not place.strip():
        return None
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", place).lower().strip()
    words = cleaned.split()
    compact = "".join(words)
    if compact in KNOWN_LOCATIONS:
        return KNOWN_LOCATIONS[compact]
    for w in words:
        if len(w) >= 3 and w in KNOWN_LOCATIONS:
            return KNOWN_LOCATIONS[w]
    return None


@lru_cache(maxsize=256)
def _geocode_nominatim(place: str) -> tuple[float, float] | None:
    query = place.strip()
    if not query:
        return None
    for attempt in range(2):
        try:
            response = httpx.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "in"},
                headers={"User-Agent": "CropMandiAI-HarvestRoute/2.0"},
                timeout=12.0,
            )
            response.raise_for_status()
            results = response.json()
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
            break
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            if attempt == 0:
                time.sleep(0.5)
    return None


def _geocode(place: str) -> tuple[float, float] | None:
    """Geocode helper: checks fast curated locations first, then Nominatim."""
    known = _resolve_known(place)
    if known is not None:
        return known
    res = _geocode_nominatim(place)
    return res


def _road_route(
    origin: tuple[float, float], destination: tuple[float, float]
) -> dict[str, Any] | None:
    """Return route metrics and GeoJSON geometry from OSRM.

    OSRM coordinates are longitude,latitude; the public API response is
    converted to Leaflet-ready GeoJSON for the Harvest Route map.
    """
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    )
    for attempt in range(2):
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
            if attempt == 0:
                time.sleep(0.5)
    return None


def _price_per_kg(price: float, unit: str | None, commodity: str = "") -> float | None:
    label = (unit or "").lower().replace(" ", "")
    if not label:
        if commodity.lower() == "pepper" and price > 0:
            return price  # Indian black pepper trade prices are standard in Rs/kg
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


# ---------------------------------------------------------------------------
# Vegetable / multi-crop rankings (re-uses main.py crop_rankings)
# ---------------------------------------------------------------------------

def _get_vegetable_rankings(session: Session, commodity: str, series: str | None, limit: int) -> dict[str, Any]:
    """Return rankings-payload shaped dict for vegetable crops."""
    try:
        from ml.crop_prediction_service import crop_rankings
        import json
        variety, grade = None, None
        if series:
            try:
                parsed = json.loads(series)
                if isinstance(parsed, list) and len(parsed) >= 2:
                    variety, grade = parsed[0], parsed[1]
            except Exception:
                variety = series
        result = crop_rankings(session, commodity, variety, grade, limit=limit)
        return result
    except Exception:
        return {"rankings": [], "unit": "Rs./Quintal"}


# ---------------------------------------------------------------------------
# Main harvest routes payload
# ---------------------------------------------------------------------------

def harvest_routes_payload(session: Session, payload: HarvestRouteRequest) -> dict[str, Any]:
    """Build the full HarvestRoute response with vehicle-aware cost engine."""

    # 1. Get market rankings
    commodity_lower = payload.commodity.lower()
    is_vegetable = commodity_lower in {"tomato", "maize", "paddy", "potato"}

    if is_vegetable:
        rankings_payload_data = _get_vegetable_rankings(
            session, commodity_lower, payload.series, payload.limit
        )
    else:
        rankings_payload_data = market_rankings_payload(
            session,
            parse_commodity(payload.commodity),
            series=payload.series,
            limit=payload.limit,
        )
        # If rice has no price_observations, gracefully fall back to paddy market observations
        if not rankings_payload_data.get("rankings") and commodity_lower == "rice":
            paddy_data = _get_vegetable_rankings(session, "paddy", payload.series, payload.limit)
            if paddy_data.get("rankings"):
                rankings_payload_data = paddy_data
                rankings_payload_data["selected_series"] = "Paddy (Common / Dhan)"
                rankings_payload_data["unit_note"] = "Showing APMC Paddy mandi observations as proxy for raw rice crop."

    rankings = rankings_payload_data.get("rankings") or []
    if not rankings:
        raise HTTPException(
            status_code=404,
            detail="No market ranking data is available for this crop/variety yet.",
        )

    # 2. Geocode farm origin
    origin_coords: tuple[float, float] | None = None
    if payload.latitude is not None and payload.longitude is not None:
        origin_coords = (payload.latitude, payload.longitude)
    else:
        origin_coords = _geocode(f"{payload.origin}, India")
    if origin_coords is None:
        raise HTTPException(
            status_code=422,
            detail="Could not locate the farm location. Enter a clearer village/town and district, or use the GPS button.",
        )

    # 3. Resolve vehicle
    price_unit = rankings_payload_data.get("unit")
    vehicle_spec: dict[str, Any] | None = None
    vehicle_validation: dict[str, Any] | None = None

    if payload.vehicle_mode == "manual" and payload.vehicle_id:
        v = get_vehicle_by_id(payload.vehicle_id)
        if v is None:
            raise HTTPException(
                status_code=400,
                detail=f"Vehicle ID '{payload.vehicle_id}' not found in catalogue. "
                       f"Use GET /api/harvest/vehicles for the list.",
            )
        vehicle_spec = v
        vehicle_validation = validate_payload(payload.vehicle_id, payload.quantity_kg)
    # In "auto" mode, vehicle selection happens per-mandi in rank_markets

    # 4. Build candidate list (geocode + route for each market)
    candidates: list[dict[str, Any]] = []

    for index, market in enumerate(rankings):
        places = market.get("locations") or []
        town = str(places[0]) if places else str(market.get("market_name") or "").strip()
        destination_query = (
            f"{town}, Karnataka, India" if town
            else f"{market.get('market_name')}, India"
        )

        # 1. Try town query
        destination_coords = _geocode(destination_query)
        # 2. Try raw town name
        if destination_coords is None and town:
            destination_coords = _geocode(town)
        # 3. Try raw market name
        if destination_coords is None:
            destination_coords = _geocode(str(market.get("market_name") or ""))
        price = float(market.get("price") or 0.0)
        price_per_kg_val = _price_per_kg(price, price_unit or market.get("unit"), payload.commodity)

        base = {
            "rank": market.get("rank", index + 1),
            "market_name": market.get("market_name"),
            "town": town,
            "price": price,
            "price_per_kg": price_per_kg_val,
            "unit": price_unit or market.get("unit"),
            "price_date": market.get("date"),
            "price_freshness": market.get("freshness_status"),
            "route_url": "https://www.google.com/maps/dir/?" + urlencode({
                "api": "1",
                "origin": payload.origin,
                "destination": destination_query,
                "travelmode": "driving",
            }),
        }

        if destination_coords is None:
            candidates.append({
                **base,
                "distance_km": None,
                "duration_min": None,
                "destination_coordinates": None,
                "route_geometry": None,
                "route_status": "destination_not_geocoded",
                "gross_estimate_inr": None,
                "transport_estimate_inr": None,
                "net_estimate_inr": None,
            })
            continue

        route = _road_route(origin_coords, destination_coords)
        distance = route["distance_km"] if route else None
        duration = route["duration_min"] if route else None

        # Legacy flat-rate estimate (backward compat, shown as fallback)
        flat_rate = payload.transport_cost_per_km
        legacy_transport = round(distance * flat_rate, 2) if (distance is not None and flat_rate is not None) else None
        legacy_gross = round(price_per_kg_val * payload.quantity_kg, 2) if price_per_kg_val is not None else None
        legacy_net = round(legacy_gross - legacy_transport, 2) if (legacy_gross is not None and legacy_transport is not None) else None

        candidates.append({
            **base,
            "distance_km": round(distance, 1) if distance is not None else None,
            "duration_min": round(duration) if duration is not None else None,
            "destination_coordinates": [destination_coords[0], destination_coords[1]],
            "route_geometry": route.get("geometry") if route else None,
            "route_status": "road_route_available" if route else "route_unavailable",
            # Legacy estimates (may be overwritten by optimizer)
            "gross_estimate_inr": legacy_gross,
            "transport_estimate_inr": legacy_transport,
            "net_estimate_inr": legacy_net,
        })

        if index < len(rankings) - 1:
            time.sleep(1.0)

    # 5. Run smart mandi optimizer
    ranked_markets = rank_markets(
        commodity=commodity_lower,
        candidates=candidates,
        quantity_kg=payload.quantity_kg,
        vehicle_mode=payload.vehicle_mode,
        vehicle=vehicle_spec,
        ownership=payload.ownership,
        round_trip=False,
    )

    # 6. Build vehicle summary for the response header
    vehicle_header: dict[str, Any] = {}
    if payload.vehicle_mode == "manual" and vehicle_spec:
        vehicle_header = {
            "mode": "manual",
            "vehicle_id": vehicle_spec["id"],
            "vehicle_model": vehicle_spec["model"],
            "vehicle_category": vehicle_spec["category"],
            "usable_payload_kg": vehicle_spec["usable_payload_kg"],
            "ownership": payload.ownership,
            "overload_warning": vehicle_validation.get("warning") if vehicle_validation else None,
        }
    else:
        vehicle_header = {
            "mode": "auto",
            "note": "Vehicle selected per mandi to minimise transport cost. See vehicle_summary in each market card.",
            "ownership": payload.ownership,
        }

    return {
        "commodity": payload.commodity,
        "selected_series": rankings_payload_data.get("selected_series"),
        "origin": payload.origin,
        "origin_coordinates": [origin_coords[0], origin_coords[1]],
        "quantity_kg": payload.quantity_kg,
        "vehicle": vehicle_header,
        # Keep legacy key for old clients
        "transport_cost_per_km": payload.transport_cost_per_km,
        "price_unit": price_unit,
        "unit_note": rankings_payload_data.get("unit_note"),
        "markets": ranked_markets,
        "ranking_method": (
            "Highest estimated net realization after vehicle-specific transport cost, "
            "APMC market fee (2%) and handling — when price unit and road distance are available. "
            "Falls back to reported market price when distance or price unit is unavailable."
        ),
        "data_status": rankings_payload_data.get("data_status"),
        "source": rankings_payload_data.get("source"),
        "limitations": [
            "Route endpoints use geocoded town centres, not verified individual mandi gates.",
            "OSRM public demo routing and OpenStreetMap geocoding are best-effort services without a production SLA.",
            "Transport rates are CONFIGURED_ESTIMATE values from industry references; not live transporter quotations.",
            "A net estimate is shown only when the source price unit can safely be converted to INR per kg and a road distance is available.",
            "Actual trader bids, tolls, taxes, return-trip costs and spoilage may differ from estimates shown.",
            "Vehicle operating costs sourced from IRTMF/AITWA fleet-operator cost indices 2024; update when fuel or labour costs change.",
        ],
    }


# ---------------------------------------------------------------------------
# Router endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
def harvest_route_health() -> dict[str, str]:
    return {
        "feature": "harvest-route",
        "status": "available",
        "routing": "OSRM public demo; no API key required",
        "version": "v2-vehicle-aware",
    }


@router.get("/vehicles")
def list_vehicles() -> dict[str, Any]:
    """Return the full vehicle catalogue with operating cost specs."""
    vehicles = get_all_vehicles()
    return {
        "vehicles": vehicles,
        "count": len(vehicles),
        "note": (
            "Operating cost components are CONFIGURED_ESTIMATE values from industry references. "
            "Hire rates are typical market quotations, not live transporter bids. "
            "Verify with local transporters before dispatch."
        ),
    }


@router.get("/fuel-price")
def fuel_price() -> dict[str, Any]:
    """Return current diesel and petrol reference prices."""
    return {
        "diesel": get_diesel_price(),
        "petrol": get_petrol_price(),
        "note": "Live PPAC API not integrated. Values are CONFIGURED_ESTIMATE. Update admin config when prices change.",
    }
