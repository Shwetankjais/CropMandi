from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from apps.api.analytics import analytics_response
from apps.api.crop_intelligence import router as crop_intelligence_router
from apps.api.cold_storage import location_payload, nearby_payload
from apps.api.errors import ApiError
from apps.api.market_centres import available_payload, centres_payload, locations_payload, prices_payload
from apps.api.market_rankings import market_rankings_payload
from apps.api.payments import router as payment_router
from apps.api.services import estimate_response, history_response, latest_response, parse_commodity
from apps.api.weather import weather_payload
from cropmandi.db.session import create_all, make_session_factory
from cropmandi_voice_assistant import create_voice_router
from cropmandi_voice_assistant.project_adapter import make_project_price_lookup

create_all()
SessionLocal = make_session_factory()
app = FastAPI(
    title="CropMandi AI V1 Data API",
    version="0.4.0",
    description="Latest prices, history, market-centre records, vegetable ML experiments, Mappls location/routing, HarvestRoute, cold-storage and weather data, demo Razorpay payments, and a Hindi/English/Kannada voice assistant.",
)
app.state.session_factory = SessionLocal
app.include_router(payment_router, prefix="/api/payment")
app.include_router(crop_intelligence_router)
app.include_router(
    create_voice_router(
        price_lookup=make_project_price_lookup(SessionLocal),
        navigation_routes={
            "dashboard": "/cropmandi_ai_dashboard/code.html",
            "cold_storage": "/cropmandi_ai_dashboard/code.html#dash-storage-heading",
            "recommendations": "/cropmandi_ai_dashboard/code.html#dash-rec-title",
            "payments": "/cropmandi_ai_dashboard/code.html#dash-pay-button",
            "settings": "/cropmandi_ai_settings/code.html",
            "home": "/index.html",
            "weather": "/cropmandi_ai_dashboard/code.html#dash-weather-temp",
        },
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return exc.to_response()


@app.exception_handler(RequestValidationError)
def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_request",
            "message": "Request could not be parsed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, ApiError):
        return exc.to_response()
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred"},
    )


def _db() -> Session:
    return SessionLocal()


@app.get("/api/prices/latest")
def latest_prices(commodity: str = Query(..., min_length=1)):
    session = _db()
    try:
        return latest_response(session, parse_commodity(commodity))
    finally:
        session.close()


@app.get("/api/prices/history")
def price_history(
    commodity: str = Query(..., min_length=1),
    series: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
):
    session = _db()
    try:
        return history_response(
            session,
            parse_commodity(commodity),
            series,
            date_from,
            date_to,
        )
    finally:
        session.close()


@app.get("/api/markets")
def list_markets(commodity: str = Query(..., min_length=1)):
    return locations_payload(parse_commodity(commodity))


@app.get("/api/markets/centres")
def list_market_centres(
    commodity: str = Query(..., min_length=1),
    location: str = Query(..., min_length=1),
):
    return centres_payload(parse_commodity(commodity), location)


@app.get("/api/markets/available")
def list_market_available(
    commodity: str = Query(..., min_length=1),
    location: str = Query(..., min_length=1),
):
    return available_payload(parse_commodity(commodity), location)


@app.get("/api/markets/prices")
def list_market_prices(
    commodity: str = Query(..., min_length=1),
    location: str = Query(..., min_length=1),
):
    return prices_payload(parse_commodity(commodity), location)


@app.get("/api/markets/rankings")
def list_market_rankings(
    commodity: str = Query(..., min_length=1),
    series: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=5),
):
    session = _db()
    try:
        return market_rankings_payload(
            session,
            parse_commodity(commodity),
            series=series,
            limit=limit,
        )
    finally:
        session.close()


@app.get("/api/predictions/next")
def next_session_estimate(
    commodity: str = Query(..., min_length=1),
    series: str | None = Query(default=None),
):
    session = _db()
    try:
        return estimate_response(session, parse_commodity(commodity), series)
    finally:
        session.close()


@app.get("/api/cold-storages")
def list_cold_storages(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    crop: str | None = Query(default=None),
    quantity_kg: float | None = Query(default=None, ge=0),
    district: str | None = Query(default=None),
    max_distance_km: float = Query(default=100, ge=1, le=500),
    limit: int = Query(default=5, ge=1, le=20),
):
    return nearby_payload(
        latitude=latitude,
        longitude=longitude,
        crop=crop,
        quantity_kg=quantity_kg,
        district=district,
        max_distance_km=max_distance_km,
        limit=limit,
    )


@app.get("/api/cold-storage")
def cold_storage_for_location(
    location: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
):
    return location_payload(location=location, limit=limit)


@app.get("/api/weather")
def weather_for_location(location: str = Query(..., min_length=1)):
    return weather_payload(location)


@app.get("/api/analytics")
def analytics_data(
    commodity: str = Query(..., min_length=1),
    location: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
):
    session = _db()
    try:
        return analytics_response(session, parse_commodity(commodity), location, days)
    finally:
        session.close()
