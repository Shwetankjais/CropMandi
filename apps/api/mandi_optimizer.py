"""Smart Mandi Optimizer for HarvestRoute.

Calculates per-mandi net realization and ranks candidates by profitability,
not by proximity.

Formula
-------
Gross Revenue     = price_per_kg × sellable_quantity_kg
Market Fee        = Gross Revenue × MARKET_FEE_FRACTION   (APMC 2%)
Handling Cost     = (quantity_kg / 100) × HANDLING_COST_PER_QUINTAL
Transport Cost    = from vehicle_service.calculate_transport_cost()
Net Realization   = Gross Revenue - Market Fee - Handling Cost - Transport Cost

All monetary values INR. Quantities in kg.
"""
from __future__ import annotations

from typing import Any, Literal

from apps.api.vehicle_catalogue import (
    DURABLE_LOSS_FRACTION,
    HANDLING_COST_PER_QUINTAL,
    MARKET_FEE_FRACTION,
    PERISHABLE_CROPS,
    PERISHABLE_LOSS_FRACTION,
)
from apps.api.vehicle_service import calculate_transport_cost, recommend_vehicle


def _quality_loss_fraction(commodity: str, distance_km: float) -> float:
    """Return spoilage/quality-loss fraction for a given crop and distance.

    For perishable crops the loss scales with distance (capped at 5%).
    For durable crops a fixed conservative loss applies.
    """
    if commodity.lower() in PERISHABLE_CROPS:
        # 1% per 100 km, capped at 5%
        return min(PERISHABLE_LOSS_FRACTION * (distance_km / 100.0), 0.05)
    return DURABLE_LOSS_FRACTION


def calculate_net_realization(
    *,
    commodity: str,
    price_per_kg: float,
    quantity_kg: float,
    distance_km: float,
    vehicle: dict[str, Any],
    ownership: Literal["owned", "hired"],
    round_trip: bool = False,
) -> dict[str, Any]:
    """Return a full profit breakdown for a single candidate mandi.

    Returns
    -------
    dict with:
      price_per_kg            float
      quantity_kg             float
      loss_fraction           float
      sellable_quantity_kg    float
      gross_revenue           float
      market_fee              float
      handling_cost           float
      transport_cost_detail   dict  (from vehicle_service)
      total_transport_cost    float
      net_realization         float
      net_per_kg              float
      effective_cost_per_kg   float
    """
    # Quality loss
    loss_frac = _quality_loss_fraction(commodity, distance_km)
    sellable_kg = quantity_kg * (1.0 - loss_frac)

    # Revenue
    gross_revenue = price_per_kg * sellable_kg

    # Market fee (APMC commission)
    market_fee = gross_revenue * MARKET_FEE_FRACTION

    # Handling (loading + unloading)
    quintals = quantity_kg / 100.0
    handling_cost = quintals * HANDLING_COST_PER_QUINTAL

    # Transport
    transport_detail = calculate_transport_cost(
        vehicle, quantity_kg, distance_km, ownership, round_trip=round_trip
    )
    total_transport = transport_detail["total_transport_cost"]

    # Net
    total_deductions = market_fee + handling_cost + total_transport
    net_realization = gross_revenue - total_deductions
    net_per_kg = net_realization / quantity_kg if quantity_kg else 0.0
    effective_cost_per_kg = total_deductions / quantity_kg if quantity_kg else 0.0

    return {
        "price_per_kg": round(price_per_kg, 4),
        "quantity_kg": quantity_kg,
        "loss_fraction": round(loss_frac, 4),
        "sellable_quantity_kg": round(sellable_kg, 2),
        "gross_revenue": round(gross_revenue, 2),
        "market_fee": round(market_fee, 2),
        "handling_cost": round(handling_cost, 2),
        "transport_cost_detail": transport_detail,
        "total_transport_cost": round(total_transport, 2),
        "total_deductions": round(total_deductions, 2),
        "net_realization": round(net_realization, 2),
        "net_per_kg": round(net_per_kg, 4),
        "effective_cost_per_kg": round(effective_cost_per_kg, 4),
    }


def rank_markets(
    *,
    commodity: str,
    candidates: list[dict[str, Any]],
    quantity_kg: float,
    vehicle_mode: Literal["auto", "manual"],
    vehicle: dict[str, Any] | None,
    ownership: Literal["owned", "hired"],
    round_trip: bool = False,
) -> list[dict[str, Any]]:
    """Rank candidate mandis by net realization (highest first).

    Each candidate dict must have:
      market_name, town, price (per unit), unit, distance_km (may be None),
      duration_min, gross_estimate_inr, route_geometry, destination_coordinates,
      route_url, route_status, rank, price_date, price_freshness.

    Adds to each candidate:
      profit_breakdown        dict (from calculate_net_realization)
      net_estimate_inr        float | None
      transport_estimate_inr  float | None
      vehicle_summary         dict
      recommendation_basis    str
      recommendation_order    int
    """
    ranked: list[dict[str, Any]] = []

    for mkt in candidates:
        distance_km: float | None = mkt.get("distance_km")

        if distance_km is None or mkt.get("price") is None:
            # Cannot calculate net; fall back to price-only ordering
            mkt["profit_breakdown"] = None
            mkt["net_estimate_inr"] = None
            mkt["transport_estimate_inr"] = None
            mkt["vehicle_summary"] = None
            mkt["recommendation_basis"] = (
                "Price only — route distance unavailable; vehicle cost not calculated."
            )
            ranked.append(mkt)
            continue

        # Pick vehicle
        if vehicle_mode == "auto" or vehicle is None:
            v = recommend_vehicle(quantity_kg, distance_km, ownership)
            used_vehicle = v  # dict from vehicle_service (has vehicle_id etc.)
            # Extract the vehicle spec dict back
            from apps.api.vehicle_catalogue import get_vehicle_by_id
            vehicle_spec = get_vehicle_by_id(v["vehicle_id"]) or v
        else:
            vehicle_spec = vehicle
            v = calculate_transport_cost(
                vehicle_spec, quantity_kg, distance_km, ownership,
                round_trip=round_trip
            )
            used_vehicle = v

        price_per_kg = mkt.get("price_per_kg")
        if price_per_kg is None or price_per_kg <= 0:
            mkt["profit_breakdown"] = None
            mkt["net_estimate_inr"] = None
            mkt["transport_estimate_inr"] = used_vehicle.get("total_transport_cost")
            mkt["vehicle_summary"] = _vehicle_summary(used_vehicle)
            mkt["recommendation_basis"] = (
                "Transport cost calculated; mandi selling price unit unknown — net estimate unavailable."
            )
            ranked.append(mkt)
            continue

        breakdown = calculate_net_realization(
            commodity=commodity,
            price_per_kg=price_per_kg,
            quantity_kg=quantity_kg,
            distance_km=distance_km,
            vehicle=vehicle_spec,
            ownership=ownership,
            round_trip=round_trip,
        )

        mkt["profit_breakdown"] = breakdown
        mkt["net_estimate_inr"] = breakdown["net_realization"]
        mkt["gross_estimate_inr"] = breakdown["gross_revenue"]
        mkt["transport_estimate_inr"] = breakdown["total_transport_cost"]
        mkt["vehicle_summary"] = _vehicle_summary(used_vehicle)
        mkt["recommendation_basis"] = (
            f"Net realization after transport ({used_vehicle.get('vehicle_category', '')}, "
            f"{used_vehicle.get('trips', 1)} trip(s)), market fee (2%) and handling."
        )
        ranked.append(mkt)

    # Sort: mandis with net realization first (highest first), then price-only
    comparable = [m for m in ranked if m.get("net_estimate_inr") is not None]
    no_route = [m for m in ranked if m.get("net_estimate_inr") is None]

    comparable.sort(key=lambda m: -m["net_estimate_inr"])
    no_route.sort(key=lambda m: (m.get("price") is None, -(m.get("price") or 0)))

    result = comparable + no_route
    for i, mkt in enumerate(result, start=1):
        mkt["recommendation_order"] = i

    return result


def _vehicle_summary(cost_detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "vehicle_id": cost_detail.get("vehicle_id"),
        "vehicle_model": cost_detail.get("vehicle_model"),
        "vehicle_category": cost_detail.get("vehicle_category"),
        "usable_payload_kg": cost_detail.get("usable_payload_kg"),
        "trips": cost_detail.get("trips"),
        "base_rate_per_km": cost_detail.get("base_rate_per_km"),
        "rate_type": cost_detail.get("rate_type"),
        "total_transport_cost": cost_detail.get("total_transport_cost"),
        "effective_cost_per_kg": cost_detail.get("effective_cost_per_kg"),
        "confidence": cost_detail.get("confidence"),
        "data_source": cost_detail.get("data_source"),
        "last_verified": cost_detail.get("last_verified"),
    }

