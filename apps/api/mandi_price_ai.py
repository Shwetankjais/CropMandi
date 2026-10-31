"""Mandi Price AI — FastAPI router for the 4-crop ExtraTreesRegressor pipeline.

This module integrates the ``best_price_model.joblib`` (ExtraTreesRegressor
Pipeline trained on Paddy, Tomato, Potato, and Maize *processed* feature CSVs)
and exposes a ``predict_price`` endpoint at ``/api/mandi-price/*``.

Zero-regression design:
  - No existing route, model, or schema is modified.
  - The existing per-crop RandomForest models in ``ml/artifacts/*.pkl`` are
    **completely untouched**; this module loads only ``best_price_model.joblib``.
  - Feature engineering exactly mirrors the ``Pilepine.ipynb`` notebook logic.
"""
from __future__ import annotations

import math
import warnings
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths — anchored to the project root (parent of apps/)
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[2]
_MODEL_PATH = _ROOT / "ml" / "artifacts" / "best_price_model.joblib"
_FEAT_PATH  = _ROOT / "ml" / "artifacts" / "feature_columns.joblib"
_PLOT_PATH  = _ROOT / "ml" / "artifacts" / "evaluation_plots.png"

# CSV feature files live in datasets/ (copied from processed/)
_DATASETS_DIR = _ROOT / "datasets"

SUPPORTED_CROPS = {"maize", "paddy", "potato", "tomato"}

router = APIRouter(prefix="/api/mandi-price", tags=["mandi-price-ai"])


# ---------------------------------------------------------------------------
# Model & data loading (cached — only loaded once per process)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_pipeline():
    """Load the ExtraTreesRegressor pipeline. Raises FileNotFoundError if absent."""
    if not _MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Mandi Price AI model not found at {_MODEL_PATH}. "
            "Copy DATASET/models/best_price_model.joblib to ml/artifacts/."
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return joblib.load(_MODEL_PATH)


@lru_cache(maxsize=1)
def _load_feature_columns() -> list[str]:
    """Load the feature column list used during training."""
    if not _FEAT_PATH.exists():
        raise FileNotFoundError(
            f"Feature columns file not found at {_FEAT_PATH}."
        )
    return list(joblib.load(_FEAT_PATH))


@lru_cache(maxsize=1)
def _load_combined_df() -> pd.DataFrame:
    """Load and concatenate all four processed crop feature CSVs.

    The engineer_features() transformation exactly mirrors the notebook so
    the column set matches what the trained pipeline expects.
    """
    dfs: list[pd.DataFrame] = []
    for crop in ("maize", "paddy", "potato", "tomato"):
        csv_path = _DATASETS_DIR / f"{crop}_features.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        dfs.append(df)
    if not dfs:
        raise FileNotFoundError(
            f"No *_features.csv files found in {_DATASETS_DIR}. "
            "Copy processed/*.csv to datasets/."
        )
    full_df = pd.concat(dfs, ignore_index=True)
    return _engineer_features(full_df)


# ---------------------------------------------------------------------------
# Feature engineering — verbatim from Pilepine.ipynb (no modifications)
# ---------------------------------------------------------------------------

def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Parses dates, handles missing values, and creates price-return & momentum features.

    This function is a direct port of engineer_features() from Pilepine.ipynb so
    that inference-time features are identical to those used during training.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "market"]).reset_index(drop=True)

    eps = 1.0

    # Target formulation (only needed for training rows — kept for column completeness)
    if "target_next_modal" in df.columns:
        df["target_pct_change"] = (
            (df["target_next_modal"] - df["modal_today"])
            / np.maximum(df["modal_today"], eps)
        )

    # Scale-invariant price momentum & ratios
    df["return_1d"]      = (df["modal_today"] - df["modal_lag1"]) / np.maximum(df["modal_lag1"], eps)
    df["return_7d"]      = (df["modal_today"] - df["modal_lag7"]) / np.maximum(df["modal_lag7"], eps)
    df["spread_ratio"]   = (df["max"]         - df["min"])        / np.maximum(df["modal_today"], eps)
    df["arrival_anomaly"] = df["arrivals"] / np.maximum(df["arrivals_roll_mean"], eps)

    # Cyclical calendar features
    df["day_of_year"] = df["date"].dt.dayofyear
    df["dow_sin"]     = np.sin(2 * np.pi * df["dow"]   / 7)
    df["dow_cos"]     = np.cos(2 * np.pi * df["dow"]   / 7)
    df["month_sin"]   = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"]   = np.cos(2 * np.pi * df["month"] / 12)

    # Fill lag/roll columns per-market
    lag_cols = [c for c in df.columns if "lag" in c or "roll" in c]
    for col in lag_cols:
        df[col] = df.groupby("market")[col].transform(lambda x: x.ffill().bfill())
        df[col] = df[col].fillna(df["modal_today"])

    df["min"] = df["min"].fillna(df["modal_today"])
    df["max"] = df["max"].fillna(df["modal_today"])
    df = df.fillna(0)
    return df


# ---------------------------------------------------------------------------
# Core predict_price function — verbatim logic from Pilepine.ipynb
# ---------------------------------------------------------------------------

def predict_price(
    crop: str,
    market: str,
    target_date_str: str,
) -> float:
    """Predict the modal price for *crop* at *market* on *target_date_str*.

    For historical dates: returns the model's price estimate for that row.
    For future dates:     recursively applies the percentage-change forecast
                          for each day between the latest observation and the
                          target date (mirrors the notebook's multi-day path).

    Args:
        crop:            One of maize / paddy / potato / tomato (case-insensitive).
        market:          Market name as it appears in the feature CSV (case-insensitive).
        target_date_str: ISO date string e.g. "2026-11-15".

    Returns:
        Predicted modal price (float, INR/quintal).

    Raises:
        ValueError:       If no historical data exists for the crop+market pair.
        FileNotFoundError: If model artifacts or CSVs are missing.
    """
    model        = _load_pipeline()
    feature_cols = _load_feature_columns()
    data_df      = _load_combined_df()
    target_date  = pd.to_datetime(target_date_str)

    sub_df = data_df[
        (data_df["crop"].str.upper()   == crop.upper()) &
        (data_df["market"].str.upper() == market.upper())
    ].sort_values("date")

    if sub_df.empty:
        raise ValueError(
            f"No historical data found for Crop='{crop}', Market='{market}'. "
            "Check that the market name matches the CSV exactly."
        )

    latest_date = sub_df["date"].max()

    if target_date <= latest_date:
        # Historical / in-sample prediction
        row = sub_df[sub_df["date"] == target_date]
        if row.empty:
            row = sub_df.iloc[[-1]]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            pct_pred = float(model.predict(row[feature_cols])[0])
        return float(row["modal_today"].values[0] * (1.0 + pct_pred))

    # Recursive multi-day future forecasting
    days_ahead = (target_date - latest_date).days
    curr_row   = sub_df.iloc[-1].copy()
    curr_price = float(curr_row["modal_today"])

    for _ in range(days_ahead):
        lag1 = float(curr_row.get("modal_lag1", curr_price))
        lag7 = float(curr_row.get("modal_lag7", curr_price))
        curr_row["return_1d"]    = (curr_price - lag1) / max(lag1, 1.0)
        curr_row["return_7d"]    = (curr_price - lag7) / max(lag7, 1.0)
        curr_row["modal_lag1"]   = curr_price
        curr_row["modal_today"]  = curr_price
        pred_input = pd.DataFrame([curr_row[feature_cols]])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            pct_pred = float(model.predict(pred_input)[0])
        curr_price *= (1.0 + pct_pred)
        if not math.isfinite(curr_price) or curr_price < 0:
            break

    return float(curr_price)


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class MandiPricePredictRequest(BaseModel):
    """Request body for the predict endpoint."""
    crop:    Literal["maize", "paddy", "potato", "tomato"]
    market:  str = Field(min_length=1, max_length=255,
                         description="Market name (case-insensitive) as in the feature CSV.")
    target_date: date | None = Field(
        default=None,
        description="ISO date to predict for. Defaults to tomorrow if omitted."
    )

    class Config:
        extra = "ignore"


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
def mandi_price_health() -> dict:
    """Return model readiness status without loading heavy data."""
    model_ready = _MODEL_PATH.exists() and _FEAT_PATH.exists()
    datasets_ready = all(
        (_DATASETS_DIR / f"{c}_features.csv").exists()
        for c in SUPPORTED_CROPS
    )
    return {
        "success":        True,
        "service":        "mandi-price-ai",
        "model_artifact": str(_MODEL_PATH),
        "model_ready":    model_ready,
        "datasets_ready": datasets_ready,
        "supported_crops": sorted(SUPPORTED_CROPS),
    }


@router.get("/markets")
def list_markets(crop: str) -> dict:
    """List all markets available for the given crop in the feature data."""
    crop_lower = crop.strip().lower()
    if crop_lower not in SUPPORTED_CROPS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported crop '{crop}'. Choose from: {sorted(SUPPORTED_CROPS)}"
        )
    try:
        df = _load_combined_df()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    sub = df[df["crop"].str.upper() == crop_lower.upper()]
    markets = sorted(sub["market"].dropna().unique().tolist())
    return {
        "crop":    crop_lower,
        "count":   len(markets),
        "markets": markets,
    }


@router.post("/predict")
def predict_mandi_price(body: MandiPricePredictRequest) -> dict:
    """Predict the modal price for a crop+market on a given date.

    Uses the ExtraTreesRegressor pipeline (``best_price_model.joblib``) trained
    on all four crop feature CSVs. For future dates, the forecast is recursive
    (uncertainty increases with horizon).
    """
    target_date = body.target_date or (date.today() + timedelta(days=1))
    try:
        predicted = predict_price(body.crop, body.market, str(target_date))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed unexpectedly: {exc}"
        ) from exc

    return {
        "success":              True,
        "crop":                 body.crop,
        "market":               body.market,
        "target_date":          str(target_date),
        "predicted_modal_price": round(predicted, 2),
        "unit":                 "INR/quintal (approximate — verify against actual mandi rates)",
        "model":                "ExtraTreesRegressor pipeline (best_price_model.joblib)",
        "model_kind":           "percentage_change_then_apply_to_base_price",
        "data_status":          "USER_SUPPLIED_AGMARKNET_EXPORT_UNVERIFIED",
        "important_note": (
            "This is an experimental forecast from historical AGMARKNET data. "
            "It is not an official market price and must not be used as a guaranteed sale quote."
        ),
    }


@router.get("/crops/summary")
def crop_summary() -> dict:
    """Return a brief summary of each crop's available data and model status."""
    try:
        df = _load_combined_df()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    results = []
    for crop in sorted(SUPPORTED_CROPS):
        sub = df[df["crop"].str.upper() == crop.upper()]
        market_count = int(sub["market"].nunique()) if not sub.empty else 0
        row_count    = int(len(sub))
        date_min     = str(sub["date"].min().date()) if not sub.empty else None
        date_max     = str(sub["date"].max().date()) if not sub.empty else None
        results.append({
            "crop":          crop,
            "row_count":     row_count,
            "market_count":  market_count,
            "date_range_from": date_min,
            "date_range_to":   date_max,
        })

    model_ready = _MODEL_PATH.exists() and _FEAT_PATH.exists()
    return {
        "model_artifact": "best_price_model.joblib",
        "model_type":     "ExtraTreesRegressor pipeline",
        "model_ready":    model_ready,
        "crops":          results,
    }

