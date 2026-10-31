"""Routes for the four supplied, trained crop-price models."""
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.api.multi_crop_model_service import (
    MODEL_CONFIG, ModelInputError, get_model_info, load_model, predict,
)

router = APIRouter(tags=["Multi-crop AI price prediction"])

class CropPredictionRequest(BaseModel):
    prediction_date: date = Field(description="Date associated with the forecast row")
    features: dict[str, Any] = Field(description="Numeric feature values required by this model")

@router.get("/api/ai-crops")
def ai_crop_models():
    return {"models": [{"crop": crop, "display_name": cfg["display_name"], "prediction_kind": cfg["prediction_kind"], "features": list(cfg["features"]), "input_features": list(cfg["input_features"]), "requires_engineered_features": cfg["requires_engineered"]} for crop, cfg in MODEL_CONFIG.items()]}

@router.get("/api/ai-crops/health")
def ai_crop_models_health():
    result = {}
    for crop in MODEL_CONFIG:
        try:
            model = load_model(crop)
            result[crop] = {"status": "ok", "n_features": int(model.n_features_in_), "n_estimators": len(model.estimators_)}
        except Exception as exc:
            result[crop] = {"status": "error", "error": str(exc)}
    return {"status": "ok" if all(v["status"] == "ok" for v in result.values()) else "degraded", "models": result}

@router.get("/api/ai-crops/{crop}/model-info")
def ai_crop_model_info(crop: str):
    try:
        return get_model_info(crop)
    except ModelInputError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load model: {exc}") from exc

@router.post("/api/ai-crops/{crop}/predict")
def predict_ai_crop(crop: str, request: CropPredictionRequest):
    try:
        result = predict(crop, request.features, request.prediction_date)
        config = MODEL_CONFIG[result.crop]
        return {"crop": result.crop, "display_name": config["display_name"], "prediction_kind": result.prediction_kind, "prediction_label": result.prediction_label, "prediction": result.prediction, "target_unit": "training target units; confirm against source dataset", "target_horizon": "not recorded in supplied model artifact", "prediction_date": result.prediction_date.isoformat(), "tree_diagnostics": {"min": result.tree_min, "max": result.tree_max, "standard_deviation": result.tree_std, "note": "Tree disagreement is not a calibrated prediction interval."}, "features_used": result.features, "requires_engineered_features": config["requires_engineered"]}
    except ModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}") from exc
