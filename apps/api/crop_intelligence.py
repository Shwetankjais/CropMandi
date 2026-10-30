"""API routes for supplied vegetable datasets, ML models and HarvestRoute."""
from __future__ import annotations

from datetime import date
from typing import Literal
import secrets

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cropmandi.db.models import CropMarketObservation, MandiLocation
from ml.crop_prediction_service import (
    CropModelError, MODEL_CONFIG, crop_options, crop_rankings,
    model_registry, predict_from_history,
)
from apps.api.location_services import MapplsClient, MapplsError, haversine_km

router = APIRouter(tags=["crop-intelligence", "location", "harvestroute"])


def _session(request: Request) -> Session:
    factory = request.app.state.session_factory
    return factory()


class PredictionRequest(BaseModel):
    crop: Literal["tomato", "maize", "paddy", "potato"]
    market_name: str = Field(min_length=1, max_length=255)
    district: str | None = None
    variety: str = Field(min_length=1, max_length=128)
    grade: str = Field(min_length=1, max_length=128)
    prediction_date: date | None = None


class Coordinate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LocationCaptureRequest(Coordinate):
    accuracy_m: float | None = Field(default=None, ge=0)
    purpose: Literal["farm", "collection_point", "current_phone_location"] = "current_phone_location"
    language: str = "en"


class ReverseGeocodeRequest(Coordinate):
    language: str = "en"


class GeocodeMandiRequest(BaseModel):
    mandi_id: int


class AddressGeocodeRequest(BaseModel):
    address: str = Field(min_length=3, max_length=500)


class MatrixRequest(BaseModel):
    origin: Coordinate
    destinations: list[dict] = Field(min_length=1, max_length=99)
    profile: Literal["driving", "biking", "trucking"] = "driving"


class HarvestRouteRequest(BaseModel):
    origin: Coordinate
    crop: Literal["tomato", "maize", "paddy", "potato"]
    variety: str | None = None
    grade: str | None = None
    quantity_quintal: float = Field(gt=0, le=100000)
    profile: Literal["driving", "biking", "trucking"] = "trucking"
    rate_per_km: float = Field(default=20, ge=0, le=10000)
    fixed_transport_cost: float = Field(default=0, ge=0, le=1000000)
    handling_cost: float = Field(default=0, ge=0, le=1000000)
    round_trip: bool = True
    market_fee_percent: float = Field(default=0, ge=0, le=100)
    loss_percent: float = Field(default=0, ge=0, lt=100)
    market_purchase_limit_quintal: float | None = Field(default=None, gt=0)
    radius_km: float = Field(default=100, gt=0, le=500)


@router.get("/api/crops/models")
def list_crop_models(request: Request):
    session = _session(request)
    try:
        return model_registry(session)
    finally:
        session.close()


@router.get("/api/crops/options")
def list_crop_options(request: Request, crop: str = Query(...)):
    session = _session(request)
    try:
        try:
            return crop_options(session, crop)
        except CropModelError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


@router.get("/api/crops/history")
def crop_market_history(
    request: Request,
    crop: str = Query(...), market_name: str = Query(...), variety: str = Query(...), grade: str = Query(...),
    district: str | None = None, limit: int = Query(default=60, ge=1, le=500),
):
    session = _session(request)
    try:
        stmt = select(CropMarketObservation).where(
            CropMarketObservation.crop_code == crop.lower(),
            CropMarketObservation.market_name == market_name,
            CropMarketObservation.variety == variety,
            CropMarketObservation.grade == grade,
        )
        if district:
            stmt = stmt.where(CropMarketObservation.district == district)
        rows = session.scalars(stmt.order_by(CropMarketObservation.market_date.desc()).limit(limit)).all()
        return {
            "crop": crop.lower(), "market_name": market_name, "variety": variety, "grade": grade,
            "count": len(rows), "records": [
                {"date": r.market_date.isoformat(), "arrivals": float(r.arrivals), "unit": r.unit,
                 "min_price": float(r.min_price) if r.min_price is not None else None,
                 "max_price": float(r.max_price) if r.max_price is not None else None,
                 "modal_price": float(r.modal_price), "data_status": r.data_status}
                for r in reversed(rows)
            ],
        }
    finally:
        session.close()


@router.get("/api/crops/rankings")
def list_crop_rankings(
    request: Request, crop: str = Query(...), variety: str | None = None,
    grade: str | None = None, limit: int = Query(default=10, ge=1, le=100),
):
    session = _session(request)
    try:
        if crop.lower() not in MODEL_CONFIG:
            raise HTTPException(status_code=400, detail="Crop must be tomato, maize, paddy or potato.")
        return crop_rankings(session, crop.lower(), variety, grade, limit)
    finally:
        session.close()


@router.post("/api/crops/predict")
def predict_crop_price(body: PredictionRequest, request: Request):
    session = _session(request)
    try:
        try:
            return predict_from_history(
                session, body.crop, body.market_name, body.district, body.variety, body.grade, body.prediction_date,
            )
        except CropModelError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        session.close()


@router.get("/api/mandis")
def list_mandis(request: Request, district: str | None = None, limit: int = Query(default=250, ge=1, le=500)):
    session = _session(request)
    try:
        stmt = select(MandiLocation)
        if district:
            stmt = stmt.where(MandiLocation.district.ilike(f"%{district}%"))
        rows = session.scalars(stmt.order_by(MandiLocation.district, MandiLocation.name).limit(limit)).all()
        return {"count": len(rows), "mandis": [
            {"id": r.id, "name": r.name, "district": r.district, "state": r.state,
             "latitude": float(r.latitude) if r.latitude is not None else None,
             "longitude": float(r.longitude) if r.longitude is not None else None,
             "coordinate_status": r.coordinate_status, "is_verified": bool(r.is_verified), "source": r.source}
            for r in rows
        ]}
    finally:
        session.close()


@router.get("/api/location/map-config")
def map_config():
    client = MapplsClient()
    from cropmandi.config import get_settings
    settings = get_settings()
    return {
        "provider": "Mappls", "map_sdk_configured": bool(settings.mappls_map_sdk_key),
        "map_sdk_key": settings.mappls_map_sdk_key or None,
        "rest_api_configured": client.configured,
        "notice": "The map SDK key is intended to be domain-restricted in Mappls Console. REST key is never returned.",
    }


@router.post("/api/location/geocode")
def forward_geocode(body: AddressGeocodeRequest):
    try:
        result = MapplsClient().geocode(body.address)
        return {"provider": "Mappls", **result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mappls geocoding failed: {exc}") from exc


@router.post("/api/location/reverse-geocode")
def reverse_geocode(body: ReverseGeocodeRequest):
    try:
        return MapplsClient().reverse_geocode(body.latitude, body.longitude, body.language)
    except httpx_error_types() as exc:
        raise HTTPException(status_code=502, detail=f"Mappls reverse geocoding failed: {exc}") from exc


def httpx_error_types():
    import httpx
    return (httpx.HTTPError, MapplsError)


@router.post("/api/location/capture")
def capture_farmer_location(body: LocationCaptureRequest):
    # Coordinates are intentionally not persisted by this endpoint. Store farm
    # location only after an explicit product consent/save action is implemented.
    result = MapplsClient().reverse_geocode(body.latitude, body.longitude, body.language)
    return {
        "latitude": body.latitude, "longitude": body.longitude, "accuracy_m": body.accuracy_m,
        "purpose": body.purpose, "stored": False, "privacy": "Coordinates are processed for this request and are not persisted.",
        "reverse_geocode": result,
    }


@router.post("/api/mandis/geocode")
def geocode_mandi(body: GeocodeMandiRequest, request: Request):
    session = _session(request)
    try:
        mandi = session.get(MandiLocation, body.mandi_id)
        if mandi is None:
            raise HTTPException(status_code=404, detail="Mandi record not found.")
        address = ", ".join(x for x in (mandi.name, mandi.district, mandi.state, "India") if x)
        try:
            found = MapplsClient().geocode(address)
        except MapplsError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Mappls geocoding failed: {exc}") from exc
        mandi.latitude = found["latitude"]
        mandi.longitude = found["longitude"]
        mandi.coordinate_status = "MAPPLS_SUGGESTED_UNVERIFIED"
        mandi.is_verified = False
        mandi.mappls_eloc = found.get("mappls_eloc")
        session.commit()
        return {
            "mandi_id": mandi.id, "name": mandi.name, "district": mandi.district,
            "latitude": found["latitude"], "longitude": found["longitude"],
            "formatted_address": found.get("formatted_address"), "confidence": found.get("confidence"),
            "coordinate_status": mandi.coordinate_status,
            "message": "Coordinates are a Mappls suggestion. Confirm the actual market gate/location before using them for farmer recommendations.",
        }
    finally:
        session.close()


@router.post("/api/mandis/{mandi_id}/confirm")
def confirm_mandi_coordinates(mandi_id: int, body: Coordinate, request: Request):
    from cropmandi.config import get_settings
    expected_token = get_settings().mandi_coordinate_admin_token
    supplied_token = request.headers.get("X-Mandi-Admin-Token", "")
    if not expected_token:
        raise HTTPException(status_code=503, detail="Mandi coordinate approval is disabled. Configure MANDI_COORDINATE_ADMIN_TOKEN on the server.")
    if not supplied_token or not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=403, detail="A valid mandi-coordinate admin token is required.")
    session = _session(request)
    try:
        mandi = session.get(MandiLocation, mandi_id)
        if mandi is None:
            raise HTTPException(status_code=404, detail="Mandi record not found.")
        mandi.latitude = body.latitude
        mandi.longitude = body.longitude
        mandi.coordinate_status = "MANUALLY_CONFIRMED"
        mandi.is_verified = True
        session.commit()
        return {"mandi_id": mandi.id, "coordinate_status": mandi.coordinate_status, "is_verified": True}
    finally:
        session.close()


@router.get("/api/markets/nearby")
def nearby_mandis(
    request: Request,
    latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(default=100, ge=1, le=500), limit: int = Query(default=10, ge=1, le=50),
    profile: Literal["driving", "biking", "trucking"] = "driving",
):
    session = _session(request)
    try:
        rows = session.scalars(select(MandiLocation).where(
            MandiLocation.latitude.is_not(None), MandiLocation.longitude.is_not(None),
        )).all()
        nearby = []
        for r in rows:
            straight = haversine_km(latitude, longitude, float(r.latitude), float(r.longitude))
            if straight <= radius_km:
                nearby.append({"id": r.id, "name": r.name, "district": r.district, "state": r.state,
                               "latitude": float(r.latitude), "longitude": float(r.longitude),
                               "coordinate_status": r.coordinate_status, "is_verified": bool(r.is_verified),
                               "straight_line_km": straight})
        nearby.sort(key=lambda x: x["straight_line_km"])
        nearby = nearby[:limit]
        if not nearby:
            return {"origin": {"latitude": latitude, "longitude": longitude}, "count": 0, "mandis": [],
                    "message": "No geocoded mandi records are in the selected radius. Use the mandi directory to geocode and verify candidates."}
        matrix = MapplsClient().distance_matrix({"latitude": latitude, "longitude": longitude}, nearby, profile)
        return {"origin": {"latitude": latitude, "longitude": longitude}, "radius_km": radius_km,
                "provider": matrix["provider"], "is_road_distance": matrix.get("is_road_distance", False),
                "notice": matrix.get("notice"), "count": len(matrix["results"]), "mandis": matrix["results"]}
    finally:
        session.close()


@router.post("/api/routes/matrix")
def calculate_route_matrix(body: MatrixRequest):
    try:
        return MapplsClient().distance_matrix(
            {"latitude": body.origin.latitude, "longitude": body.origin.longitude},
            body.destinations, body.profile,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Route matrix could not be calculated: {exc}") from exc


@router.post("/api/harvestroute/optimize")
def optimize_harvest_route(body: HarvestRouteRequest, request: Request):
    session = _session(request)
    try:
        stmt = select(CropMarketObservation).where(CropMarketObservation.crop_code == body.crop)
        if body.variety:
            stmt = stmt.where(CropMarketObservation.variety == body.variety)
        if body.grade:
            stmt = stmt.where(CropMarketObservation.grade == body.grade)
        observations = session.scalars(stmt.order_by(CropMarketObservation.market_date.desc())).all()
        latest = {}
        for r in observations:
            key = (r.market_name, r.district, r.variety, r.grade)
            if key not in latest or r.market_date > latest[key].market_date:
                latest[key] = r
        mandi_rows = session.scalars(select(MandiLocation).where(
            MandiLocation.latitude.is_not(None), MandiLocation.longitude.is_not(None),
            MandiLocation.is_verified.is_(True),
        )).all()
        mandi_lookup = {(r.name.casefold(), r.district.casefold()): r for r in mandi_rows}
        candidates = []
        for (market, district, variety, grade), obs in latest.items():
            mandi = mandi_lookup.get((market.casefold(), district.casefold()))
            if mandi is None:
                continue
            straight = haversine_km(body.origin.latitude, body.origin.longitude, float(mandi.latitude), float(mandi.longitude))
            if straight <= body.radius_km:
                candidates.append({
                    "id": mandi.id, "name": mandi.name, "district": mandi.district,
                    "latitude": float(mandi.latitude), "longitude": float(mandi.longitude),
                    "straight_line_km": straight, "price": float(obs.modal_price), "price_date": obs.market_date.isoformat(),
                    "unit": obs.unit, "variety": variety, "grade": grade,
                    "is_verified": bool(mandi.is_verified), "coordinate_status": mandi.coordinate_status,
                })
        if not candidates:
            return {"crop": body.crop, "count": 0, "results": [],
                    "message": "No priced markets with coordinates were found. Geocode market candidates and confirm their coordinates first.",
                    "transport_inputs": body.model_dump(exclude={"origin", "crop", "variety", "grade"})}
        candidates.sort(key=lambda x: x["straight_line_km"])
        candidates = candidates[:25]
        matrix = MapplsClient().distance_matrix(
            {"latitude": body.origin.latitude, "longitude": body.origin.longitude}, candidates, body.profile,
        )
        rows = []
        for route in matrix["results"]:
            distance = route.get("distance_km")
            if distance is None:
                continue
            travel_km = distance * (2 if body.round_trip else 1)
            transport_cost = travel_km * body.rate_per_km + body.fixed_transport_cost
            sellable_quantity = body.quantity_quintal * (1 - body.loss_percent / 100)
            if body.market_purchase_limit_quintal:
                sellable_quantity = min(sellable_quantity, body.market_purchase_limit_quintal)
            gross = sellable_quantity * route["price"]
            market_fee = gross * body.market_fee_percent / 100
            net = gross - transport_cost - market_fee - body.handling_cost
            rows.append({
                **route,
                "sellable_quantity_quintal": round(sellable_quantity, 3),
                "gross_sale_value": round(gross, 2),
                "transport_cost": round(transport_cost, 2),
                "market_fee": round(market_fee, 2),
                "handling_cost": round(body.handling_cost, 2),
                "estimated_net_return": round(net, 2),
            })
        rows.sort(key=lambda x: -x["estimated_net_return"])
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
        return {
            "crop": body.crop, "quantity_quintal": body.quantity_quintal,
            "provider": matrix["provider"], "is_road_distance": matrix.get("is_road_distance", False),
            "notice": matrix.get("notice"), "count": len(rows), "results": rows,
            "ranking_method": "Estimated net return after configurable transport, market-fee, handling and loss assumptions.",
            "price_data_status": "USER_SUPPLIED_AGMARKNET_EXPORT_UNVERIFIED",
            "important_note": "Market prices are historical observations, not live offers. Transport costs are user-entered estimates. Coordinates must be verified. This is decision support, not a guaranteed sale quote.",
        }
    finally:
        session.close()
