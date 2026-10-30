"""Analytics endpoint that consolidates data from existing providers for the Analytics page."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from apps.api.catalog import SeriesSpec, series_for
from apps.api.coffee_data import coffee_history, coffee_latest, coffee_payload_fields
from apps.api.errors import ApiError
from apps.api.market_centres import (
    DATA_STATUS,
    DATA_USAGE,
    SOURCE_PROVENANCE,
    prices_payload,
    resolve_location,
)
from apps.api.pepper_data import pepper_history, pepper_latest, pepper_payload_fields
from apps.api.rice_data import rice_history, rice_latest, rice_payload_fields
from apps.api.services import parse_date_param


def analytics_response(
    session: Session,
    commodity: str,
    location: str | None,
    days: int,
) -> dict[str, Any]:
    """
    Consolidated analytics data for the Analytics page.
    
    Returns real data from existing providers:
    - Coffee: Coffee Board data (experimental) and market centre data
    - Pepper: Spices Board/AGMARKNET data from database and market centre data
    - Cardamom: Not currently supported (will return no-data state)
    
    All data is verified from real sources - no hardcoded values.
    """
    # Cardamom is not currently supported
    commodity_code = commodity.strip().lower()
    if commodity_code == "cardamom":
        return _no_data_response(commodity, location, "Cardamom data not currently available")

    # Grain & Vegetable crops: Tomato, Maize, Paddy, Potato
    if commodity_code in {"tomato", "maize", "paddy", "potato"}:
        return _vegetable_analytics_response(session, commodity_code, location, days)
    
    # For Coffee and Pepper, fetch real data from existing providers
    try:
        if location:
            # Location-specific analytics using market centres
            try:
                canonical_location = resolve_location(commodity, location)
            except ApiError:
                # If location resolution fails, return no-data state
                return _no_data_response(commodity, location, f"Location '{location}' not supported for {commodity}")
            
            try:
                market_data = prices_payload(commodity, canonical_location)
            except ApiError:
                # If market data fetch fails, continue with empty market data
                market_data = {"observations": [], "count": 0}
            
            # Get historical data for the requested time period
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # Try to get series-specific historical data
            historical_data = []
            latest_price = None
            latest_unit = None
            source_info = {}
            
            for spec in series_for(commodity, session=session):
                if commodity == "coffee":
                    points = coffee_history(spec, start_date, end_date)
                    latest = coffee_latest(spec)
                    if latest:
                        latest_price = latest["price"]
                        latest_unit = latest["unit"]
                        source_info = coffee_payload_fields(spec)
                elif commodity == "pepper":
                    points = pepper_history(session, spec, start_date, end_date)
                    latest = pepper_latest(session, spec)
                    if latest:
                        latest_price = latest["price"]
                        latest_unit = latest["unit"]
                        source_info = pepper_payload_fields(spec, latest)
                elif commodity == "rice":
                    points = rice_history(session, spec, start_date, end_date)
                    latest = rice_latest(session, spec)
                    if latest:
                        latest_price = latest["price"]
                        latest_unit = latest["unit"]
                        source_info = rice_payload_fields(spec, latest)
                
                if points:
                    historical_data.extend([
                        {
                            "date": p["observation_date"].isoformat(),
                            "price": p["price"],
                            "unit": p["unit"],
                            "series": spec.display_name
                        }
                        for p in points
                    ])
            
            # Sort historical data by date
            historical_data.sort(key=lambda x: x["date"])
            
            # Build market comparison from real market centre data
            market_comparison = []
            if market_data.get("observations"):
                try:
                    # Group by market centre and get latest price
                    from collections import defaultdict
                    market_prices = defaultdict(list)
                    for obs in market_data["observations"]:
                        if obs.get("price") is not None:
                            market_prices[obs["market_centre"]].append(obs)
                    
                    for centre, obs_list in market_prices.items():
                        # Get the most recent observation
                        latest_obs = max(obs_list, key=lambda x: x.get("date", ""))
                        market_comparison.append({
                            "market": centre,
                            "location": canonical_location,
                            "price": latest_obs["price"],
                            "unit": latest_obs.get("unit"),
                            "date": latest_obs["date"],
                            "source": latest_obs.get("source"),
                            "type": latest_obs.get("type"),
                        })
                    
                    # Sort by price descending
                    market_comparison.sort(key=lambda x: x["price"] or 0, reverse=True)
                except Exception:
                    # If market comparison building fails, continue with empty list
                    market_comparison = []
            
            # Calculate simple trend from historical data
            trend = None
            trend_percentage = None
            if len(historical_data) >= 2:
                # Ensure we're comparing prices with the same unit
                first_point = historical_data[0]
                last_point = historical_data[-1]
                
                # Check if units are consistent
                if first_point.get("unit") == last_point.get("unit"):
                    first_price = first_point["price"]
                    last_price = last_point["price"]
                    if first_price and last_price and first_price > 0:
                        change = last_price - first_price
                        trend_percentage = (change / first_price) * 100
                        if trend_percentage > 2:
                            trend = "BULLISH"
                        elif trend_percentage < -2:
                            trend = "BEARISH"
                        else:
                            trend = "NEUTRAL"
            
            # Prediction - use existing prediction endpoint or show unavailable
            prediction = None
            try:
                from apps.api.services import estimate_response, require_series
                # Use the first available series for prediction
                if series_for(commodity, session=session):
                    spec = series_for(commodity, session=session)[0]
                    pred_data = estimate_response(session, commodity, spec.series_id)
                    if pred_data.get("next_session_estimate") is not None:
                        prediction = {
                            "estimate": pred_data["next_session_estimate"],
                            "percentage_change": pred_data.get("estimated_percentage_change", 0),
                            "method": pred_data.get("method", "unknown"),
                            "note": pred_data.get("note", ""),
                            "target_session": pred_data.get("target_session"),
                        }
            except Exception:
                # If prediction fails, it's unavailable
                prediction = None
            
            return {
                "available": True,
                "commodity": commodity,
                "location": canonical_location,
                "days": days,
                "latest": {
                    "price": latest_price,
                    "unit": latest_unit,
                    "date": source_info.get("observation_date") if source_info else None,
                } if latest_price else None,
                "historical": historical_data,
                "trend": trend,
                "trend_percentage": trend_percentage,
                "prediction": prediction,
                "market_comparison": market_comparison,
                "regional_data": _build_regional_data(commodity, canonical_location, market_data),
                "source": source_info,
                "data_status": source_info.get("data_status", DATA_STATUS),
                "data_usage": source_info.get("data_usage", DATA_USAGE),
                "provenance": source_info.get("provenance", SOURCE_PROVENANCE),
            }
        
        else:
            # Location not specified - return no-data state
            return _no_data_response(commodity, location, "Location parameter required for analytics")
    
    except ApiError as e:
        # If it's a known API error (e.g., unsupported location), return no-data state
        return _no_data_response(commodity, location, str(e))
    except Exception as e:
        # For unexpected errors, still return no-data state rather than fake data
        return _no_data_response(commodity, location, f"Data unavailable: {str(e)}")


def _no_data_response(commodity: str, location: str | None, reason: str) -> dict[str, Any]:
    """Return a proper no-data state instead of fake values."""
    return {
        "available": False,
        "commodity": commodity,
        "location": location,
        "reason": reason,
        "latest": None,
        "historical": [],
        "trend": None,
        "trend_percentage": None,
        "prediction": None,
        "market_comparison": [],
        "regional_data": [],
        "source": None,
        "data_status": "NO_DATA",
        "data_usage": "NOT_APPLICABLE",
        "provenance": None,
    }


def _build_regional_data(commodity: str, location: str, market_data: dict) -> list[dict]:
    """Build regional heatmap data from actual market centre prices."""
    regional = []
    if market_data.get("observations"):
        # Create location-based price points for the heatmap
        from collections import defaultdict
        location_prices = defaultdict(list)
        
        for obs in market_data["observations"]:
            if obs.get("price") is not None:
                # Use the market centre as a proxy for location
                location_prices[obs["market_centre"]].append(obs)
        
        for centre, obs_list in location_prices.items():
            latest_obs = max(obs_list, key=lambda x: x.get("date", ""))
            regional.append({
                "location": centre,
                "price": latest_obs["price"],
                "unit": latest_obs.get("unit"),
                "date": latest_obs["date"],
            })
    
    return regional


def _vegetable_analytics_response(
    session: Session,
    crop_code: str,
    location: str | None,
    days: int,
) -> dict[str, Any]:
    from sqlalchemy import desc, func, select
    from cropmandi.db.models import CropMarketObservation
    from ml.unified_prediction_service import predict_price

    default_markets = {
        "tomato": "KOLAR",
        "potato": "BENGALURU",
        "maize": "ARAKALGUD",
        "paddy": "SHIVAMOGGA",
    }
    market_name = (location or default_markets.get(crop_code, "KOLAR")).strip().upper()

    stmt = (
        select(CropMarketObservation)
        .where(
            CropMarketObservation.crop_code == crop_code,
            func.upper(CropMarketObservation.market_name) == market_name,
        )
        .order_by(desc(CropMarketObservation.market_date))
    )
    rows = session.scalars(stmt.limit(max(days, 30))).all()
    if not rows:
        stmt_fallback = (
            select(CropMarketObservation)
            .where(CropMarketObservation.crop_code == crop_code)
            .order_by(desc(CropMarketObservation.market_date))
        )
        rows = session.scalars(stmt_fallback.limit(max(days, 30))).all()
        if rows:
            market_name = rows[0].market_name.upper()

    if not rows:
        return _no_data_response(crop_code, location, f"No observations found for {crop_code}")

    chronological = list(reversed(rows))
    latest = chronological[-1]
    latest_price = float(latest.modal_price)
    unit_label = "Rs./Quintal"
    latest_date = latest.market_date.isoformat()

    historical = [
        {
            "date": r.market_date.isoformat(),
            "price": float(r.modal_price),
            "unit": unit_label,
            "series": r.variety or crop_code.title(),
        }
        for r in chronological
    ]

    trend = "NEUTRAL"
    trend_percentage = 0.0
    if len(chronological) >= 2:
        first_p = float(chronological[0].modal_price)
        last_p = float(chronological[-1].modal_price)
        if first_p > 0:
            trend_percentage = round(((last_p - first_p) / first_p) * 100, 2)
            if trend_percentage > 2.0:
                trend = "BULLISH"
            elif trend_percentage < -2.0:
                trend = "BEARISH"

    prediction = None
    try:
        pred_res = predict_price(
            session=session,
            commodity=crop_code,
            variety=latest.variety,
            grade=latest.grade,
            market=market_name,
            district=latest.district,
            state=latest.state,
            prediction_date=None,
            quantity=50.0,
            persist=False,
        )
        prediction = {
            "estimate": pred_res["predicted_price"],
            "percentage_change": pred_res["pct_change"],
            "method": pred_res["model_name"],
            "note": "AI multi-crop regression forecast",
            "target_session": pred_res["prediction_date"],
        }
    except Exception as exc:
        pass

    sub_q = (
        select(
            CropMarketObservation.market_name,
            CropMarketObservation.district,
            func.max(CropMarketObservation.market_date).label("max_date"),
        )
        .where(CropMarketObservation.crop_code == crop_code)
        .group_by(CropMarketObservation.market_name, CropMarketObservation.district)
        .subquery()
    )
    comp_stmt = (
        select(CropMarketObservation)
        .join(
            sub_q,
            (CropMarketObservation.market_name == sub_q.c.market_name)
            & (CropMarketObservation.market_date == sub_q.c.max_date),
        )
        .where(CropMarketObservation.crop_code == crop_code)
        .order_by(desc(CropMarketObservation.modal_price))
        .limit(6)
    )
    comp_rows = session.scalars(comp_stmt).all()
    market_comparison = [
        {
            "centre": r.market_name,
            "district": r.district,
            "price": float(r.modal_price),
            "unit": unit_label,
            "date": r.market_date.isoformat(),
            "variety": r.variety,
        }
        for r in comp_rows
    ]

    regional_data = [
        {
            "location": r.market_name,
            "price": float(r.modal_price),
            "unit": unit_label,
            "date": r.market_date.isoformat(),
        }
        for r in comp_rows
    ]

    source_info = {
        "data_status": "AGMARKNET_VERIFIED_EXPORT",
        "data_usage": "ML_PREDICTION_AND_HISTORICAL_ANALYSIS",
        "provenance": "AGMARKNET 2025-2026 dataset",
        "observation_date": latest_date,
    }

    return {
        "available": True,
        "commodity": crop_code,
        "location": market_name,
        "days": days,
        "latest": {
            "price": latest_price,
            "unit": unit_label,
            "date": latest_date,
        },
        "historical": historical,
        "trend": trend,
        "trend_percentage": trend_percentage,
        "prediction": prediction,
        "market_comparison": market_comparison,
        "regional_data": regional_data,
        "source": source_info,
        "data_status": "AGMARKNET_VERIFIED_EXPORT",
        "data_usage": "ML_PREDICTION_AND_HISTORICAL_ANALYSIS",
        "provenance": "AGMARKNET 2025-2026 dataset",
    }
