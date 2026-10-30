"""Mappls REST adapter plus explicit straight-line fallback for development."""
from __future__ import annotations

import math
from typing import Any
from urllib.parse import quote

import httpx

from cropmandi.config import get_settings


class MapplsError(RuntimeError):
    pass


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class MapplsClient:
    MATRIX_BASE = "https://route.mappls.com/route/dm"
    SEARCH_BASE = "https://search.mappls.com/search/address"

    def __init__(self, rest_key: str | None = None, timeout: float | None = None, client: httpx.Client | None = None):
        settings = get_settings()
        self.rest_key = rest_key if rest_key is not None else settings.mappls_rest_api_key
        self.timeout = timeout or settings.mappls_api_timeout
        self.client = client or httpx.Client(timeout=self.timeout)

    @property
    def configured(self) -> bool:
        return bool(self.rest_key)

    def reverse_geocode(self, latitude: float, longitude: float, language: str = "en") -> dict[str, Any]:
        if not self.configured:
            return {"configured": False, "message": "Mappls REST key is not configured."}
        response = self.client.get(
            f"{self.SEARCH_BASE}/rev-geocode",
            params={"lat": latitude, "lng": longitude, "access_token": self.rest_key, "lang": language},
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        return {"configured": True, "provider": "Mappls", "result": results[0] if results else None, "raw_response_code": payload.get("responseCode")}

    def geocode(self, address: str) -> dict[str, Any]:
        if not self.configured:
            raise MapplsError("Mappls REST key is not configured. Add MAPPLS_REST_API_KEY to .env.")
        response = self.client.get(
            f"{self.SEARCH_BASE}/geocode",
            params={"address": address, "itemCount": 3, "access_token": self.rest_key},
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        if not results:
            raise MapplsError("Mappls did not return a matching coordinate for this market.")
        first = results[0]
        latitude = first.get("latitude", first.get("lat"))
        longitude = first.get("longitude", first.get("lng", first.get("lon")))
        if latitude is None or longitude is None:
            raise MapplsError("Mappls geocoding response did not include latitude/longitude.")
        return {
            "latitude": float(latitude), "longitude": float(longitude),
            "formatted_address": first.get("formatted_address") or first.get("placeName") or first.get("address"),
            "mappls_eloc": first.get("eLoc") or first.get("eloc"),
            "confidence": first.get("confidenceScore") or first.get("confidence"),
            "geocode_level": first.get("geocodeLevel"),
            "raw": first,
        }

    def distance_matrix(
        self,
        origin: dict[str, float],
        destinations: list[dict[str, Any]],
        profile: str = "driving",
        allow_approximate_fallback: bool = True,
    ) -> dict[str, Any]:
        if profile not in {"driving", "biking", "trucking"}:
            raise ValueError("profile must be driving, biking or trucking")
        if not destinations:
            return {"provider": "none", "results": []}
        if len(destinations) > 99:
            raise ValueError("A single Mappls matrix request supports at most 99 destinations plus the origin.")
        if not self.configured:
            if not allow_approximate_fallback:
                raise MapplsError("Mappls REST key is not configured.")
            return {
                "provider": "Haversine (development fallback)",
                "is_road_distance": False,
                "notice": "Mappls key not configured: distances below are straight-line approximations, not road routes or ETAs.",
                "results": [
                    {
                        **dest,
                        "distance_km": round(haversine_km(origin["latitude"], origin["longitude"], dest["latitude"], dest["longitude"]), 2),
                        "duration_minutes": None,
                        "distance_type": "STRAIGHT_LINE_APPROXIMATION",
                    }
                    for dest in destinations
                ],
            }

        coords = [f'{origin["longitude"]},{origin["latitude"]}'] + [
            f'{d["longitude"]},{d["latitude"]}' for d in destinations
        ]
        url = f"{self.MATRIX_BASE}/distance_matrix/{profile}/" + ";".join(coords)
        params = {"access_token": self.rest_key}
        if profile == "driving":
            params.update({"rtype": 0, "region": "ind"})
        response = self.client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        matrix = payload.get("results") or {}
        if isinstance(matrix, list):
            matrix = matrix[0] if matrix else {}
        if str(matrix.get("code", "")).casefold() not in {"ok", ""}:
            raise MapplsError(f"Mappls Distance Matrix returned {matrix.get('code')}.")
        distances = (matrix.get("distances") or [[]])[0]
        durations = (matrix.get("durations") or [[]])[0]
        mapped = []
        for index, dest in enumerate(destinations, start=1):
            distance_m = distances[index] if index < len(distances) else None
            duration_s = durations[index] if index < len(durations) else None
            mapped.append({
                **dest,
                "distance_km": round(float(distance_m) / 1000, 2) if distance_m is not None else None,
                "duration_minutes": round(float(duration_s) / 60, 1) if duration_s is not None else None,
                "distance_type": "MAPPLS_ROAD_ROUTE",
            })
        return {
            "provider": "Mappls", "is_road_distance": True,
            "profile": profile, "results": mapped,
            "mappls_response_code": payload.get("responseCode"),
        }
