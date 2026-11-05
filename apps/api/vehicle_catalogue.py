"""Vehicle catalogue for HarvestRoute transport cost engine.

Specifications sourced from publicly available manufacturer datasheets and
road-transport industry references. Unknown or unverified values are marked
with ``confidence`` < 1.0 and must NOT be presented to the farmer as
official/live rates.

All operating cost components (maintenance, tyre, depreciation, driver) are
CONFIGURED_ESTIMATE values based on IRTMF / AITWA fleet-operator cost indices
for Karnataka / south India.  Fuel cost is computed dynamically from the
configured diesel/petrol price.

Sources consulted:
  - Tata Motors commercial vehicle specifications (tata.com)
  - Ashok Leyland product range (ashokleyland.com)
  - Mahindra truck specifications (mahindra.com)
  - IRTMF / AITWA freight-operator cost guidelines 2023-24
  - PPAC fuel price bulletin (ppac.gov.in) — used as fallback reference
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Default diesel reference price (INR/litre) — Karnataka avg 2024-11-01
# Source: PPAC Petroleum & Natural Gas price bulletin.
# Update this via /api/harvest/fuel-price admin endpoint.
# ---------------------------------------------------------------------------
_FALLBACK_DIESEL_PRICE_PER_LITRE: float = 92.5   # INR/L — Karnataka 2024-11

# Petrol reference (for auto-rickshaw / small goods auto)
_FALLBACK_PETROL_PRICE_PER_LITRE: float = 103.0  # INR/L — Karnataka 2024-11

# Market fee (mandi charge) as a fraction of gross revenue — typical APMC rate
MARKET_FEE_FRACTION: float = 0.02   # 2% commission
HANDLING_COST_PER_QUINTAL: float = 50.0  # INR — loading + unloading per quintal

# Quality/spoilage loss fraction for perishable crops
PERISHABLE_LOSS_FRACTION: float = 0.01   # 1% per 100 km (for tomato, potato, paddy)
DURABLE_LOSS_FRACTION: float = 0.005    # 0.5% — coffee, pepper, rice

PERISHABLE_CROPS = {"tomato", "potato", "paddy"}


# ---------------------------------------------------------------------------
# VEHICLE CATALOGUE
# ---------------------------------------------------------------------------
# Each entry:
#   id            str   — stable slug
#   category      str   — UI group label
#   model         str   — representative model name
#   fuel_type     str   — "diesel" | "petrol"
#   max_payload_kg  int — gross vehicle weight minus tare (manufacturer spec)
#   usable_payload_kg int — practical load; max_payload × 0.90 for safety margin
#   mileage_kmpl  float — km/litre (manufacturer ARAI/laden estimate)
#   maintenance_per_km   float — INR/km (tyres excl.)
#   tyre_per_km          float — INR/km (tyre cost amortised per km)
#   depreciation_per_km  float — INR/km (vehicle depreciation)
#   driver_per_km        float — INR/km (driver wage amortised)
#   min_hire_charge      float — INR (minimum single-trip hire)
#   base_hire_rate_per_km float — INR/km (typical quotation; hired mode)
#   data_source   str   — citation
#   last_verified str   — YYYY-MM-DD
#   confidence    float — 0–1 (1 = manufacturer-verified spec; <1 = estimate)
# ---------------------------------------------------------------------------

VEHICLES: list[dict[str, Any]] = [
    {
        "id": "goods_auto",
        "category": "Goods Auto / Cargo Three-Wheeler",
        "model": "Mahindra Alfa Cargo / Piaggio Ape Truck",
        "fuel_type": "petrol",
        "max_payload_kg": 500,
        "usable_payload_kg": 450,
        "mileage_kmpl": 30.0,
        "maintenance_per_km": 1.20,
        "tyre_per_km": 0.40,
        "depreciation_per_km": 0.80,
        "driver_per_km": 1.00,
        "min_hire_charge": 300.0,
        "base_hire_rate_per_km": 12.0,
        "data_source": "Mahindra Alfa Cargo specs; industry operator estimate",
        "last_verified": "2024-10-01",
        "confidence": 0.85,
    },
    {
        "id": "tata_ace",
        "category": "Mini Truck / Tata Ace",
        "model": "Tata Ace Gold (1-tonne)",
        "fuel_type": "diesel",
        "max_payload_kg": 1000,
        "usable_payload_kg": 900,
        "mileage_kmpl": 18.0,
        "maintenance_per_km": 1.80,
        "tyre_per_km": 0.65,
        "depreciation_per_km": 1.20,
        "driver_per_km": 1.50,
        "min_hire_charge": 500.0,
        "base_hire_rate_per_km": 18.0,
        "data_source": "Tata Motors Ace Gold GVW spec sheet; IRTMF 2024",
        "last_verified": "2024-10-01",
        "confidence": 0.90,
    },
    {
        "id": "pickup_lcv",
        "category": "Pickup / Light Commercial Vehicle",
        "model": "Mahindra Bolero Pik-Up / Tata Yodha 2.0",
        "fuel_type": "diesel",
        "max_payload_kg": 1500,
        "usable_payload_kg": 1350,
        "mileage_kmpl": 15.0,
        "maintenance_per_km": 2.10,
        "tyre_per_km": 0.80,
        "depreciation_per_km": 1.60,
        "driver_per_km": 1.80,
        "min_hire_charge": 700.0,
        "base_hire_rate_per_km": 22.0,
        "data_source": "Mahindra Bolero Pikup payload spec; IRTMF operator surveys 2024",
        "last_verified": "2024-10-01",
        "confidence": 0.85,
    },
    {
        "id": "medium_truck",
        "category": "Medium Commercial Truck",
        "model": "Tata LPT 1109 / Ashok Leyland Dost+ Heavy",
        "fuel_type": "diesel",
        "max_payload_kg": 7500,
        "usable_payload_kg": 6700,
        "mileage_kmpl": 10.0,
        "maintenance_per_km": 3.50,
        "tyre_per_km": 1.40,
        "depreciation_per_km": 3.00,
        "driver_per_km": 2.50,
        "min_hire_charge": 2000.0,
        "base_hire_rate_per_km": 32.0,
        "data_source": "Tata LPT 1109 GVW 10.5T payload spec; IRTMF 2024",
        "last_verified": "2024-10-01",
        "confidence": 0.85,
    },
    {
        "id": "truck_6w",
        "category": "6-Wheeler Truck",
        "model": "Tata LPT 1615 / Ashok Leyland Ecomet 1515",
        "fuel_type": "diesel",
        "max_payload_kg": 10000,
        "usable_payload_kg": 9000,
        "mileage_kmpl": 7.5,
        "maintenance_per_km": 5.00,
        "tyre_per_km": 2.00,
        "depreciation_per_km": 4.50,
        "driver_per_km": 3.00,
        "min_hire_charge": 3500.0,
        "base_hire_rate_per_km": 45.0,
        "data_source": "Tata LPT 1615 payload spec; IRTMF 2024",
        "last_verified": "2024-10-01",
        "confidence": 0.85,
    },
    {
        "id": "truck_10w",
        "category": "10-Wheeler / Heavy Truck",
        "model": "Tata LPT 2518 / Ashok Leyland 2518",
        "fuel_type": "diesel",
        "max_payload_kg": 16000,
        "usable_payload_kg": 14400,
        "mileage_kmpl": 5.5,
        "maintenance_per_km": 7.00,
        "tyre_per_km": 3.00,
        "depreciation_per_km": 6.50,
        "driver_per_km": 4.00,
        "min_hire_charge": 6000.0,
        "base_hire_rate_per_km": 65.0,
        "data_source": "Tata LPT 2518 GVW 25T payload spec; IRTMF 2024",
        "last_verified": "2024-10-01",
        "confidence": 0.85,
    },
    {
        "id": "multi_axle",
        "category": "Multi-Axle Truck",
        "model": "Tata Signa 4225.S / Ashok Leyland 3718",
        "fuel_type": "diesel",
        "max_payload_kg": 25000,
        "usable_payload_kg": 22500,
        "mileage_kmpl": 4.0,
        "maintenance_per_km": 10.00,
        "tyre_per_km": 4.50,
        "depreciation_per_km": 10.00,
        "driver_per_km": 5.50,
        "min_hire_charge": 10000.0,
        "base_hire_rate_per_km": 95.0,
        "data_source": "Tata Signa 4225.S GVW 42T payload spec; IRTMF 2024",
        "last_verified": "2024-10-01",
        "confidence": 0.80,
    },
]

# Build ID lookup dict
_VEHICLE_BY_ID: dict[str, dict[str, Any]] = {v["id"]: v for v in VEHICLES}


def get_all_vehicles() -> list[dict[str, Any]]:
    """Return full vehicle catalogue (safe copies)."""
    return list(VEHICLES)


def get_vehicle_by_id(vehicle_id: str) -> dict[str, Any] | None:
    """Return vehicle record by slug ID, or None if not found."""
    return _VEHICLE_BY_ID.get(vehicle_id)


def get_diesel_price() -> dict[str, Any]:
    """Return current diesel reference price with metadata.

    Future: integrate PPAC public feed. For now returns configured estimate.
    """
    return {
        "price_per_litre": _FALLBACK_DIESEL_PRICE_PER_LITRE,
        "currency": "INR",
        "source": "PPAC Petroleum Price Bulletin — Karnataka reference",
        "source_url": "https://ppac.gov.in/content/245_1_PriceofPetrolandDiesel.aspx",
        "price_type": "CONFIGURED_ESTIMATE",
        "as_of": "2024-11-01",
        "note": "Live PPAC API not integrated. Update this value via admin configuration when fuel prices change.",
    }


def get_petrol_price() -> dict[str, Any]:
    """Return current petrol reference price with metadata."""
    return {
        "price_per_litre": _FALLBACK_PETROL_PRICE_PER_LITRE,
        "currency": "INR",
        "source": "PPAC Petroleum Price Bulletin — Karnataka reference",
        "source_url": "https://ppac.gov.in/content/245_1_PriceofPetrolandDiesel.aspx",
        "price_type": "CONFIGURED_ESTIMATE",
        "as_of": "2024-11-01",
        "note": "Live PPAC API not integrated. Update this value via admin configuration when fuel prices change.",
    }

