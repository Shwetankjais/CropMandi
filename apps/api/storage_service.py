"""
AgriWise AI - Cold Storage Service

Compatible with:
GET /api/cold-storages?latitude=...&longitude=...

Expected public method:
    find_nearby_storages(
        latitude,
        longitude,
        crop=None,
        quantity_kg=None,
        district=None,
        max_distance_km=100,
        limit=5,
    )

Data source:
    CSV files in datasets/:
      - nhb_karnataka_cold_storages.csv
      - cold_storages.csv
      - demo_project_cold_storages.csv

Routing:
    OpenRouteService if ORS_API_KEY / OPENROUTESERVICE_API_KEY is configured.
    Falls back to haversine distance with an explicit routing_source flag.
"""

from __future__ import annotations

import csv
import math
import os
import time
from pathlib import Path
from typing import Any

import httpx
import requests
from dotenv import load_dotenv

from apps.api.cold_storage_match import (
    is_cold_storage_facility,
    is_exact_facility,
    load_coordinate_overlay,
    load_query_locations,
    match_type_for_distance,
    overall_match_type,
    resolve_query_location,
)
from cropmandi.config import ROOT


PROJECT_ROOT = ROOT
DATASETS_DIR = PROJECT_ROOT / "datasets"

load_dotenv(PROJECT_ROOT / ".env")


class StorageService:
    def __init__(self, data_path: str | Path | None = None):
        self.data_path = Path(data_path) if data_path else DATASETS_DIR / "cold_storages.csv"
        self.storages: list[dict[str, Any]] = []
        self._load_data()

        self.ors_api_key = (
            os.getenv("ORS_API_KEY", "").strip()
            or os.getenv("OPENROUTESERVICE_API_KEY", "").strip()
        )

        self.nominatim_enabled = (
            os.getenv("COLD_STORAGE_ENABLE_GEOCODING", "false").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.query_locations = load_query_locations()
        self.coordinate_overlay = load_coordinate_overlay()
        self._road_route_cache: dict[tuple[float, float, float, float], tuple[float | None, float | None, str]] = {}

        self._load_extra_sources()
        self._apply_coordinate_overlay()

    # ------------------------------------------------------------
    # DATA
    # ------------------------------------------------------------

    def _load_csv(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
        except Exception as exc:
            print(f"[StorageService] CSV read failed: {path}: {exc}")
            return []

        result = []
        for row in rows:
            result.append(self._normalize_storage(row))
        return result

    def _load_data(self):
        self.storages = self._load_csv(self.data_path)

    def _load_extra_sources(self):
        candidates = [
            DATASETS_DIR / "nhb_karnataka_cold_storages.csv",
            DATASETS_DIR / "demo_project_cold_storages.csv",
        ]

        by_key: dict[tuple[str, str], dict[str, Any]] = {}

        for record in self.storages:
            key = (
                self._norm(record.get("name")),
                self._norm(record.get("address")),
            )
            by_key[key] = record

        for path in candidates:
            if not path.exists():
                continue

            for record in self._load_csv(path):
                key = (
                    self._norm(record.get("name")),
                    self._norm(record.get("address")),
                )

                if key in by_key:
                    existing = by_key[key]
                    for field in (
                        "latitude",
                        "longitude",
                        "capacity_mt",
                        "district",
                        "address",
                        "source",
                    ):
                        if self._empty(existing.get(field)) and not self._empty(record.get(field)):
                            existing[field] = record[field]
                else:
                    by_key[key] = record

        self.storages = list(by_key.values())
        print(
            f"[StorageService] Loaded "
            f"{len(self.storages)} cold-storage records."
        )

    def _apply_coordinate_overlay(self) -> None:
        for record in self.storages:
            extra = self.coordinate_overlay.get(self._norm(record.get("name")))
            if not extra:
                continue
            record["latitude"] = extra["latitude"]
            record["longitude"] = extra["longitude"]
            record["coordinates_source"] = extra.get("coordinates_source") or record.get("coordinates_source")
            record["retrieved_at"] = record.get("retrieved_at") or "2026-09-06"
            if not record.get("last_verified_at"):
                record["last_verified_at"] = "2026-09-06"
            if extra.get("notes"):
                existing = str(record.get("notes") or "").strip()
                record["notes"] = f"{existing} {extra['notes']}".strip() if existing else extra["notes"]

    @staticmethod
    def _norm(value: Any) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @staticmethod
    def _empty(value: Any) -> bool:
        return value in (None, "")

    def _normalize_storage(self, row: dict[str, Any]) -> dict[str, Any]:
        def number(value):
            try:
                if value in (None, ""):
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        latitude = number(
            row.get("latitude")
            or row.get("lat")
        )

        longitude = number(
            row.get("longitude")
            or row.get("lng")
            or row.get("lon")
        )

        capacity = number(
            row.get("capacity_mt")
            or row.get("capacity")
        )

        source = str(
            row.get("source")
            or row.get("data_source")
            or "unknown"
        ).strip()
        source_url = str(row.get("source_url") or "").strip()
        if "nhb" in source.lower():
            source_type = "NHB_PROJECT_RECORD"
            verification = "NHB_PROJECT_RECORD"
            if not source_url:
                source_url = "https://nhb.gov.in/doc/karnataka.pdf"
        elif "project dataset" in source.lower():
            source_type = "UNVERIFIED"
            verification = "UNVERIFIED"
        else:
            source_type = str(row.get("source_type") or "UNVERIFIED").strip()
            verification = str(row.get("verification_status") or "UNVERIFIED").strip()

        return {
            "id": row.get("id") or row.get("document_id"),
            "document_id": row.get("document_id") or row.get("id"),
            "name": str(
                row.get("name")
                or row.get("cold_storage_name")
                or ""
            ).strip(),
            "village": str(row.get("village") or "").strip(),
            "taluk": str(row.get("taluk") or "").strip(),
            "district": str(
                row.get("district")
                or ""
            ).strip(),
            "state": str(
                row.get("state")
                or ""
            ).strip(),
            "address": str(
                row.get("address")
                or ""
            ).strip(),
            "capacity_mt": capacity,
            "supported_crops": str(
                row.get("supported_crops")
                or row.get("crops")
                or row.get("commodities_supported")
                or ""
            ).strip(),
            "storage_type": str(row.get("storage_type") or "").strip(),
            "storage_cost_per_kg_day": number(
                row.get("storage_cost_per_kg_day")
            ),
            "contact": str(
                row.get("contact")
                or row.get("phone")
                or ""
            ).strip(),
            "email": str(row.get("email") or "").strip(),
            "latitude": latitude,
            "longitude": longitude,
            "current_availability_kg": number(
                row.get("current_availability_kg")
            ),
            "source": source,
            "source_name": str(row.get("source_name") or source).strip(),
            "source_url": source_url,
            "source_type": source_type,
            "verification_status": verification,
            "last_verified_at": str(
                row.get("last_verified_at")
                or row.get("operational_checked_at")
                or row.get("retrieved_at")
                or ""
            ).strip(),
            "retrieved_at": str(row.get("retrieved_at") or "").strip(),
            "operational_status": str(
                row.get("operational_status")
                or "unknown"
            ).strip().lower(),
            "operational_checked_at": row.get(
                "operational_checked_at"
            ),
            "coordinates_source": row.get(
                "coordinates_source"
            ),
            "notes": row.get("notes") or "",
        }

    # ------------------------------------------------------------
    # GEOCODING
    # ------------------------------------------------------------

    def _geocode(self, record: dict[str, Any]) -> bool:
        if (
            record.get("latitude") is not None
            and record.get("longitude") is not None
        ):
            return True

        if not self.nominatim_enabled:
            return False

        address = record.get("address") or ""
        district = record.get("district") or ""
        state = record.get("state") or "Karnataka"

        query = ", ".join(
            part for part in [
                address,
                district,
                state,
                "India",
            ]
            if part
        )

        if not query.strip():
            return False

        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "in",
                },
                headers={
                    "User-Agent":
                        "AgriWiseAI-ColdStorage/1.0"
                },
                timeout=8,
            )

            response.raise_for_status()

            results = response.json()

            if not results:
                return False

            record["latitude"] = float(
                results[0]["lat"]
            )

            record["longitude"] = float(
                results[0]["lon"]
            )

            record["coordinates_source"] = (
                "OpenStreetMap Nominatim"
            )

            time.sleep(1)

            return True

        except Exception as exc:
            print(
                f"[StorageService] Geocoding failed "
                f"for {record.get('name')}: {exc}"
            )
            return False

    # ------------------------------------------------------------
    # DISTANCE / ROUTING
    # ------------------------------------------------------------

    @staticmethod
    def haversine_km(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        radius = 6371.0088

        p1 = math.radians(lat1)
        p2 = math.radians(lat2)

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2
            +
            math.cos(p1)
            * math.cos(p2)
            * math.sin(dlon / 2) ** 2
        )

        return radius * (
            2 * math.atan2(
                math.sqrt(a),
                math.sqrt(1 - a),
            )
        )

    def _route_ors(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> tuple[float | None, float | None]:
        if not self.ors_api_key:
            return None, None

        try:
            response = requests.get(
                "https://api.openrouteservice.org/v2/directions/driving-car",
                params={
                    "api_key": self.ors_api_key,
                    "start": f"{origin_lon},{origin_lat}",
                    "end": f"{destination_lon},{destination_lat}",
                },
                timeout=15,
            )

            response.raise_for_status()

            data = response.json()

            summary = (
                data.get("features", [{}])[0]
                .get("properties", {})
                .get("summary", {})
            )

            distance_km = (
                float(summary["distance"]) / 1000
                if summary.get("distance") is not None
                else None
            )

            eta_minutes = (
                float(summary["duration"]) / 60
                if summary.get("duration") is not None
                else None
            )

            return distance_km, eta_minutes

        except Exception as exc:
            print(
                "[StorageService] ORS routing failed:",
                exc,
            )
            return None, None

    def _route_road(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> tuple[float | None, float | None, str]:
        """Calculate road route metrics using OSRM, falling back to ORS if configured.

        Returns:
            (distance_km, eta_minutes, routing_source)
        """
        cache_key = (
            round(float(origin_lat), 4),
            round(float(origin_lon), 4),
            round(float(destination_lat), 4),
            round(float(destination_lon), 4),
        )
        if cache_key in self._road_route_cache:
            return self._road_route_cache[cache_key]

        # 1. Try OSRM (public, no API key required)
        try:
            url = (
                f"https://router.project-osrm.org/route/v1/driving/"
                f"{origin_lon},{origin_lat};{destination_lon},{destination_lat}"
            )
            resp = httpx.get(
                url,
                params={"overview": "false", "steps": "false"},
                timeout=4.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                routes = data.get("routes") or []
                if routes:
                    sel = routes[0]
                    dist_km = float(sel["distance"]) / 1000.0
                    eta_min = float(sel["duration"]) / 60.0
                    res = (dist_km, eta_min, "OSRM")
                    self._road_route_cache[cache_key] = res
                    return res
        except Exception:
            pass

        # 2. Try OpenRouteService if API key configured
        dist_ors, eta_ors = self._route_ors(
            origin_lat, origin_lon, destination_lat, destination_lon
        )
        if dist_ors is not None:
            res = (dist_ors, eta_ors, "OpenRouteService")
            self._road_route_cache[cache_key] = res
            return res

        res = (None, None, "haversine_fallback")
        self._road_route_cache[cache_key] = res
        return res

    # ------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------

    def find_nearby_storages(
        self,
        latitude: float,
        longitude: float,
        crop: str | None = None,
        quantity_kg: float | None = None,
        district: str | None = None,
        max_distance_km: float = 100,
        limit: int = 5,
    ) -> list[dict[str, Any]]:

        max_distance_km = max(
            1,
            min(float(max_distance_km), 500),
        )

        limit = max(
            1,
            min(int(limit), 20),
        )

        crop_norm = self._norm(crop)
        district_norm = self._norm(district)

        candidates = []

        for record in self.storages:
            if not is_cold_storage_facility(record):
                continue
            if record.get("verification_status") not in (
                "REGISTERED_NHB",
                "NHB_PROJECT_RECORD",
                "UNVERIFIED",
            ):
                continue

            if district_norm:
                if self._norm(record.get("district")) != district_norm:
                    continue

            if crop_norm:
                supported = self._norm(
                    record.get("supported_crops")
                )

                if (
                    supported
                    and "multi" not in supported
                    and crop_norm not in supported
                ):
                    continue

            available_kg = record.get(
                "current_availability_kg"
            )

            if (
                quantity_kg is not None
                and available_kg is not None
                and float(available_kg) < float(quantity_kg)
            ):
                continue

            if not self._geocode(record):
                continue

            if (
                record.get("latitude") is None
                or record.get("longitude") is None
            ):
                continue

            straight_distance = self.haversine_km(
                latitude,
                longitude,
                record["latitude"],
                record["longitude"],
            )

            # Pre-filter using straight-line distance.
            # Road distance will be calculated afterwards.
            if straight_distance > max_distance_km:
                continue

            candidates.append(
                (
                    straight_distance,
                    record,
                )
            )

        candidates.sort(
            key=lambda item: item[0]
        )

        results = []

        for straight_distance, record in candidates[
            : max(limit * 2, limit)
        ]:

            road_distance, eta_minutes, routing_source = self._route_road(
                latitude,
                longitude,
                record["latitude"],
                record["longitude"],
            )

            if road_distance is None:
                final_distance = straight_distance
                road_dist_val = None
                routing_source = "haversine_fallback"
                routing_note = (
                    "Road routing unavailable; "
                    "distance is straight-line estimate (Haversine)."
                )
            else:
                final_distance = road_distance
                road_dist_val = round(road_distance, 1)
                routing_note = (
                    f"Road distance and ETA from {routing_source} routing service."
                )

            if (
                final_distance > max_distance_km
            ):
                continue

            result = dict(record)

            result.update(
                {
                    "distance_km": round(
                        final_distance,
                        1,
                    ),
                    "road_distance_km": road_dist_val,
                    "eta_minutes": (
                        round(
                            eta_minutes
                        )
                        if eta_minutes is not None
                        else None
                    ),
                    "routing_source": routing_source,
                    "routing_note": routing_note,
                    "availability": "Contact facility",
                }
            )

            results.append(result)

            if len(results) >= limit:
                break

        return results

    def find_for_location(
        self,
        location_name: str,
        *,
        max_distance_km: float = 75,
        limit: int = 5,
    ) -> dict[str, Any]:
        location = resolve_query_location(location_name, self.query_locations)
        if location is None:
            return {
                "requested_location": location_name,
                "resolved_location": None,
                "match_type": "UNKNOWN_LOCATION",
                "message": "Location is not in the cold-storage query catalog.",
                "facilities": [],
            }

        lat = location.get("latitude")
        lon = location.get("longitude")
        if lat is None or lon is None:
            return {
                "requested_location": location["name"],
                "resolved_location": location,
                "match_type": "NO_DATA",
                "message": "NO VERIFIED COLD STORAGE FOUND WITHIN 75 KM.",
                "facilities": [],
            }

        scored: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        for record in self.storages:
            if not is_cold_storage_facility(record):
                continue
            if record.get("verification_status") not in ("REGISTERED_NHB", "NHB_PROJECT_RECORD", "UNVERIFIED"):
                continue
            if record.get("latitude") is None or record.get("longitude") is None:
                continue
            key = (self._norm(record.get("name")), self._norm(record.get("address")))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            straight_dist = round(
                self.haversine_km(lat, lon, record["latitude"], record["longitude"]),
                1,
            )
            exact = is_exact_facility(record, location)
            match_type = match_type_for_distance(straight_dist, exact)
            if match_type == "NO_DATA" and not exact:
                continue
            if straight_dist > max_distance_km and not exact:
                continue
            item = dict(record)
            item.update(
                {
                    "distance_km": straight_dist,
                    "straight_distance_km": straight_dist,
                    "road_distance_km": None,
                    "eta_minutes": None,
                    "routing_source": "haversine_fallback",
                    "routing_note": "Straight-line distance (Haversine).",
                    "match_type": match_type,
                    "facility_location": ", ".join(
                        part for part in (record.get("district"), record.get("state")) if part
                    ),
                    "availability": "Contact facility",
                }
            )
            scored.append(item)

        scored.sort(key=lambda row: (0 if row["match_type"] == "EXACT" else 1, row["distance_km"]))
        selected = scored[: max(1, min(int(limit), 20))]

        # Query road routing for selected facilities via OSRM
        for item in selected:
            road_dist, eta, src = self._route_road(lat, lon, item["latitude"], item["longitude"])
            if road_dist is not None:
                item["road_distance_km"] = round(road_dist, 1)
                item["eta_minutes"] = round(eta) if eta is not None else None
                item["routing_source"] = src
                item["routing_note"] = f"Road distance and travel time from {src} road routing."
            else:
                item["road_distance_km"] = None
                item["eta_minutes"] = None
                item["routing_source"] = "haversine_fallback"
                item["routing_note"] = "Road routing unavailable; distance is straight-line estimate (Haversine)."
        types = [row["match_type"] for row in selected]
        match_type = overall_match_type(types)
        message = None
        if match_type == "NO_DATA" or not selected:
            message = "NO VERIFIED COLD STORAGE FOUND WITHIN 75 KM."
            selected = []
            match_type = "NO_DATA"
        return {
            "requested_location": location["name"],
            "resolved_location": location,
            "match_type": match_type,
            "message": message,
            "facilities": selected,
        }
