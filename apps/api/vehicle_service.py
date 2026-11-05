"""Transport cost engine for HarvestRoute.

Implements:
  - Vehicle payload validation
  - Trip count calculation (CEILING division)
  - Owned-vehicle operating cost (fuel + maintenance + tyre + depreciation + driver)
  - Hired-vehicle cost (rate × distance, with minimum charge)
  - Return-journey handling
  - Full cost breakdown dict

All monetary values are in INR.
"""
from __future__ import annotations

import math
from typing import Any, Literal

from apps.api.vehicle_catalogue import (
    VEHICLES,
    get_diesel_price,
    get_petrol_price,
    get_vehicle_by_id,
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_payload(vehicle_id: str, quantity_kg: float) -> dict[str, Any]:
    """Check whether a vehicle can legally carry the quantity.

    Returns a dict with:
      ok        bool  — True if vehicle is usable
      warning   str | None — overload or over-capacity warning
      vehicle   dict  — the vehicle record
      trips     int   — number of trips required
    """
    vehicle = get_vehicle_by_id(vehicle_id)
    if vehicle is None:
        return {
            "ok": False,
            "warning": f"Vehicle ID '{vehicle_id}' not found in catalogue.",
            "vehicle": None,
            "trips": None,
        }

    usable = vehicle["usable_payload_kg"]
    trips = math.ceil(quantity_kg / usable)
    max_v = VEHICLES[-1]["usable_payload_kg"]   # largest vehicle's usable payload

    warning = None
    if quantity_kg > usable:
        if quantity_kg <= usable * 20:
            warning = (
                f"Your harvest ({quantity_kg:,.0f} kg) exceeds one vehicle load "
                f"({usable:,} kg). {trips} trip(s) will be required."
            )
        else:
            warning = (
                f"Your harvest ({quantity_kg:,.0f} kg) would require {trips} trips "
                f"with this vehicle. Consider a fleet or multiple vehicles."
            )

    return {
        "ok": True,
        "warning": warning,
        "vehicle": vehicle,
        "trips": trips,
    }


# ---------------------------------------------------------------------------
# Cost calculation helpers
# ---------------------------------------------------------------------------

def _fuel_cost_per_km(vehicle: dict[str, Any]) -> float:
    """Return INR/km fuel cost for one trip at laden weight."""
    if vehicle["fuel_type"] == "petrol":
        price = get_petrol_price()["price_per_litre"]
    else:
        price = get_diesel_price()["price_per_litre"]
    return price / vehicle["mileage_kmpl"]


def _operating_cost_per_km(vehicle: dict[str, Any]) -> float:
    """Return total operating INR/km for farmer-owned vehicle."""
    return (
        _fuel_cost_per_km(vehicle)
        + vehicle["maintenance_per_km"]
        + vehicle["tyre_per_km"]
        + vehicle["depreciation_per_km"]
        + vehicle["driver_per_km"]
    )


# ---------------------------------------------------------------------------
# Main cost calculation
# ---------------------------------------------------------------------------

def calculate_transport_cost(
    vehicle: dict[str, Any],
    quantity_kg: float,
    distance_km: float,
    ownership: Literal["owned", "hired"],
    *,
    round_trip: bool = False,
) -> dict[str, Any]:
    """Return a full transport cost breakdown.

    Parameters
    ----------
    vehicle     : vehicle record from catalogue
    quantity_kg : total harvest quantity
    distance_km : one-way road distance (from OSRM)
    ownership   : "owned" (compute operating cost) or "hired" (use hire rate)
    round_trip  : if True the vehicle returns empty; fare is for one direction only
                  (hired: typically one-way quotation; owned: add return fuel)

    Returns
    -------
    dict with keys:
      trips                   int
      one_way_distance_km     float
      effective_distance_km   float  (accounts for return if owned)
      base_rate_per_km        float
      rate_type               str
      cost_per_trip           float
      total_transport_cost    float
      effective_cost_per_kg   float
      min_charge_applied      bool
      breakdown               dict
    """
    usable = vehicle["usable_payload_kg"]
    trips = math.ceil(quantity_kg / usable)

    # For hired vehicles the transporter quotes per one-way trip.
    # For owned vehicles, the return journey consumes fuel but is at empty weight
    # (we approximate at same mileage for simplicity, with 80% fuel for empty).
    if ownership == "hired":
        base_rate = vehicle["base_hire_rate_per_km"]
        rate_type = "CONFIGURED_ESTIMATE_HIRE_RATE"
        cost_per_trip = max(
            base_rate * distance_km,
            vehicle["min_hire_charge"],
        )
        min_charge_applied = (
            base_rate * distance_km < vehicle["min_hire_charge"]
        )
        breakdown = {
            "hire_rate_per_km_inr": round(base_rate, 2),
            "one_way_fare_inr": round(base_rate * distance_km, 2),
            "min_hire_charge_inr": vehicle["min_hire_charge"],
            "cost_per_trip_inr": round(cost_per_trip, 2),
        }
        effective_distance_km = distance_km   # one-way quoted fare

    else:  # owned
        op_rate = _operating_cost_per_km(vehicle)
        base_rate = op_rate
        rate_type = "CONFIGURED_ESTIMATE_OPERATING_COST"
        fuel_rate = _fuel_cost_per_km(vehicle)
        # Return journey: only fuel + driver (lighter load)
        return_cost_per_km = fuel_rate * 0.80 + vehicle["driver_per_km"]
        cost_per_trip = op_rate * distance_km
        if round_trip:
            cost_per_trip += return_cost_per_km * distance_km
        effective_distance_km = distance_km * (2 if round_trip else 1)
        min_charge_applied = False
        breakdown = {
            "fuel_cost_per_km_inr": round(fuel_rate, 2),
            "maintenance_per_km_inr": vehicle["maintenance_per_km"],
            "tyre_per_km_inr": vehicle["tyre_per_km"],
            "depreciation_per_km_inr": vehicle["depreciation_per_km"],
            "driver_per_km_inr": vehicle["driver_per_km"],
            "total_op_rate_per_km_inr": round(op_rate, 2),
            "cost_per_trip_inr": round(cost_per_trip, 2),
        }

    total_transport_cost = cost_per_trip * trips
    effective_cost_per_kg = total_transport_cost / quantity_kg if quantity_kg else 0.0

    fuel_info = (
        get_petrol_price() if vehicle["fuel_type"] == "petrol" else get_diesel_price()
    )

    return {
        "vehicle_id": vehicle["id"],
        "vehicle_model": vehicle["model"],
        "vehicle_category": vehicle["category"],
        "usable_payload_kg": usable,
        "trips": trips,
        "one_way_distance_km": round(distance_km, 1),
        "effective_distance_km": round(effective_distance_km, 1),
        "base_rate_per_km": round(base_rate, 2),
        "rate_type": rate_type,
        "cost_per_trip": round(cost_per_trip, 2),
        "total_transport_cost": round(total_transport_cost, 2),
        "effective_cost_per_kg": round(effective_cost_per_kg, 4),
        "min_charge_applied": min_charge_applied,
        "confidence": vehicle["confidence"],
        "data_source": vehicle["data_source"],
        "last_verified": vehicle["last_verified"],
        "fuel_price_info": fuel_info,
        "breakdown": breakdown,
    }


# ---------------------------------------------------------------------------
# Auto vehicle recommendation
# ---------------------------------------------------------------------------

def recommend_vehicle(
    quantity_kg: float,
    distance_km: float,
    ownership: Literal["owned", "hired"],
) -> dict[str, Any]:
    """Select the most economical feasible vehicle for the given quantity.

    Strategy:
      1. Filter vehicles that can carry the load in a reasonable trip count
         (≤ 20 trips; beyond that the farmer should hire a fleet).
      2. Among feasible vehicles, pick the one with the lowest total transport
         cost for the full quantity.
      3. Prefer fewer trips when costs are equal (tiebreaker).

    Returns the same breakdown dict as calculate_transport_cost() plus
    ``recommendation_reason``.
    """
    best: dict[str, Any] | None = None
    best_cost: float = float("inf")

    for vehicle in VEHICLES:
        usable = vehicle["usable_payload_kg"]
        trips = math.ceil(quantity_kg / usable)
        if trips > 20:
            continue   # impractical; skip

        cost_info = calculate_transport_cost(
            vehicle, quantity_kg, distance_km, ownership
        )
        total = cost_info["total_transport_cost"]
        if total < best_cost or (
            total == best_cost and trips < (best or {}).get("trips", 9999)
        ):
            best_cost = total
            best = {**cost_info}

    if best is None:
        # Fallback: largest vehicle
        v = VEHICLES[-1]
        best = calculate_transport_cost(v, quantity_kg, distance_km, ownership)

    best["recommendation_reason"] = (
        f"Lowest estimated total transport cost (₹{best['total_transport_cost']:,.0f}) "
        f"for {quantity_kg:,.0f} kg over {distance_km:.1f} km using "
        f"{best['trips']} trip(s) with {best['vehicle_category']}."
    )
    return best

