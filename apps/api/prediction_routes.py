"""API endpoints for unified multi-crop price prediction and commodity options."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ml.unified_prediction_service import (
    get_available_commodities,
    get_commodity_options,
    get_prediction_history,
    predict_price,
)

router = APIRouter(tags=["predictions", "commodities"])


def _session(request: Request) -> Session:
    factory = request.app.state.session_factory
    return factory()


class PricePredictionRequest(BaseModel):
    commodity: str = Field(min_length=1, max_length=64)
    variety: str = Field(min_length=1, max_length=128)
    grade: str | None = Field(default="AVERAGE", max_length=128)
    market: str = Field(min_length=1, max_length=255)
    district: str | None = None
    state: str | None = "Karnataka"
    prediction_date: str | None = None
    quantity: float = Field(default=50.0, gt=0)
    quantity_unit: str = Field(default="quintal", max_length=32)
    user_id: str = Field(default="default_farmer", max_length=64)


@router.get("/api/commodities/list")
def list_commodities():
    """List all supported agricultural commodities and their model statuses."""
    return {"success": True, "commodities": get_available_commodities()}


@router.get("/api/commodities/options")
def commodity_options(request: Request, commodity: str = Query(..., min_length=1)):
    """Return available varieties, grades, and market locations for a commodity."""
    session = _session(request)
    try:
        data = get_commodity_options(session, commodity)
        data["success"] = True
        return data
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


@router.post("/api/predictions/price")
def predict_commodity_price(body: PricePredictionRequest, request: Request):
    """Execute prediction using the integrated ML pipeline or validated baseline."""
    session = _session(request)
    try:
        result = predict_price(
            session=session,
            commodity=body.commodity,
            variety=body.variety,
            grade=body.grade,
            market=body.market,
            district=body.district,
            state=body.state,
            prediction_date=body.prediction_date,
            quantity=body.quantity,
            quantity_unit=body.quantity_unit,
            user_id=body.user_id,
            persist=True,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction error: {exc}") from exc
    finally:
        session.close()


@router.get("/api/predictions/history")
def fetch_prediction_history(
    request: Request,
    user_id: str = Query(default="default_farmer"),
    commodity: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    """Retrieve saved prediction requests and outcomes for the user."""
    session = _session(request)
    try:
        items = get_prediction_history(
            session=session,
            user_id=user_id,
            commodity=commodity,
            limit=limit,
        )
        return {"user_id": user_id, "count": len(items), "history": items}
    finally:
        session.close()
