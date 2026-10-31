"""Unified prediction service for CropMandi's four supplied crop models.

IMPORTANT: only load pickle/joblib artifacts from a trusted source. Deserializing
an untrusted pickle can execute arbitrary code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
import math
from pathlib import Path
from typing import Any, Mapping
import warnings

import joblib
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models" if (BASE_DIR / "models").exists() else BASE_DIR.parents[1] / "ml" / "artifacts"

COMMON_PRICE_FEATURES = (
    "modal_today", "modal_lag1", "modal_lag2", "modal_lag3", "modal_lag7",
    "modal_roll_mean", "modal_roll_std", "arrivals_lag1", "arrivals_roll_mean",
    "spread_lag1",
)
CALENDAR_FEATURES = ("dow", "dom", "month")
ENGINEERED_FEATURES = (
    "price_dev_roll", "momentum_1d", "momentum_7d", "arrivals_log",
)

FEATURE_LABELS = {
    "modal_today": "Latest known modal price",
    "modal_lag1": "Modal price — previous market day",
    "modal_lag2": "Modal price — 2 market days ago",
    "modal_lag3": "Modal price — 3 market days ago",
    "modal_lag7": "Modal price — 7 market days ago",
    "modal_roll_mean": "Rolling mean of modal price",
    "modal_roll_std": "Rolling standard deviation of modal price",
    "arrivals_lag1": "Arrivals — previous market day",
    "arrivals_roll_mean": "Rolling mean of arrivals",
    "spread_lag1": "Price spread — previous market day",
    "dow": "Day of week (Monday=0)",
    "dom": "Day of month",
    "month": "Calendar month",
    "price_dev_roll": "Price deviation from rolling mean (precomputed)",
    "momentum_1d": "1-market-day price momentum (precomputed)",
    "momentum_7d": "7-market-day price momentum (precomputed)",
    "arrivals_log": "Log-transformed arrivals (precomputed)",
}

MODEL_CONFIG = {
    "tomato": {
        "display_name": "Tomato",
        "filename": "tomato_price_model.pkl",
        "prediction_kind": "price_level",
        "prediction_label": "Predicted modal price",
        "features": COMMON_PRICE_FEATURES + CALENDAR_FEATURES,
        "input_features": COMMON_PRICE_FEATURES,
        "requires_engineered": False,
    },
    "maize": {
        "display_name": "Maize",
        "filename": "maize_delta_rf_model.pkl",
        "prediction_kind": "delta",
        "prediction_label": "Predicted price delta",
        "features": COMMON_PRICE_FEATURES + CALENDAR_FEATURES + ENGINEERED_FEATURES,
        "input_features": COMMON_PRICE_FEATURES + ENGINEERED_FEATURES,
        "requires_engineered": True,
    },
    "paddy": {
        "display_name": "Paddy",
        "filename": "paddy_delta_rf_model.pkl",
        "prediction_kind": "delta",
        "prediction_label": "Predicted price delta",
        "features": COMMON_PRICE_FEATURES + CALENDAR_FEATURES + ENGINEERED_FEATURES,
        "input_features": COMMON_PRICE_FEATURES + ENGINEERED_FEATURES,
        "requires_engineered": True,
    },
    "potato": {
        "display_name": "Potato",
        "filename": "potato_delta_rf_model.pkl",
        "prediction_kind": "delta",
        "prediction_label": "Predicted price delta",
        "features": COMMON_PRICE_FEATURES + CALENDAR_FEATURES + ENGINEERED_FEATURES,
        "input_features": COMMON_PRICE_FEATURES + ENGINEERED_FEATURES,
        "requires_engineered": True,
    },
}

# Clearly synthetic demonstration values. Not live mandi observations.
SAMPLE_INPUTS = {
    "modal_today": 2500.0,
    "modal_lag1": 2450.0,
    "modal_lag2": 2400.0,
    "modal_lag3": 2380.0,
    "modal_lag7": 2300.0,
    "modal_roll_mean": 2400.0,
    "modal_roll_std": 120.0,
    "arrivals_lag1": 100.0,
    "arrivals_roll_mean": 110.0,
    "spread_lag1": 300.0,
    # The four engineered fields are manually supplied because the pickle
    # does not contain the preprocessing/feature-generation definitions.
    "price_dev_roll": 100.0,
    "momentum_1d": 50.0,
    "momentum_7d": 200.0,
    "arrivals_log": float(np.log1p(100.0)),
}

SIGNED_FEATURES = {"price_dev_roll", "momentum_1d", "momentum_7d"}


class ModelInputError(ValueError):
    """Raised when caller inputs do not match the model schema."""


@dataclass(frozen=True)
class PredictionResult:
    crop: str
    prediction: float
    tree_min: float
    tree_max: float
    tree_std: float
    prediction_date: date
    prediction_kind: str
    prediction_label: str
    features: dict[str, float]


def parse_prediction_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ModelInputError("Select a prediction date.")
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError as exc:
            raise ModelInputError("Prediction date must be a valid ISO date (YYYY-MM-DD).") from exc
    raise ModelInputError("Prediction date must be a date or ISO date string.")


def get_config(crop: str) -> dict[str, Any]:
    key = str(crop).strip().lower()
    if key not in MODEL_CONFIG:
        raise ModelInputError(
            f"Unknown crop '{crop}'. Available crops: {', '.join(MODEL_CONFIG)}."
        )
    return MODEL_CONFIG[key]


@lru_cache(maxsize=len(MODEL_CONFIG))
def load_model(crop: str):
    key = str(crop).strip().lower()
    config = get_config(key)
    path = MODEL_DIR / config["filename"]
    if not path.is_file():
        raise FileNotFoundError(f"Model artifact not found: {path}")

    # All supplied artifacts record sklearn 1.7.2. Use that version in
    # requirements.txt; suppress the per-tree warning only for this diagnostic
    # run under 1.8.0, but retain the compatibility note in documentation.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=r"Trying to unpickle estimator .* from version .*",
            category=UserWarning,
        )
        model = joblib.load(path)

    if not callable(getattr(model, "predict", None)):
        raise TypeError(f"{config['display_name']} artifact does not expose predict().")
    expected_features = list(config["features"])
    n_features = getattr(model, "n_features_in_", None)
    if n_features != len(expected_features):
        raise ValueError(
            f"{config['display_name']} expects {len(expected_features)} features; got {n_features}."
        )
    actual_names = list(getattr(model, "feature_names_in_", []))
    if actual_names and actual_names != expected_features:
        raise ValueError(
            f"{config['display_name']} feature order mismatch. Expected {expected_features}; "
            f"found {actual_names}."
        )
    return model


def build_feature_frame(
    crop: str, values: Mapping[str, Any], prediction_date: Any,
) -> tuple[pd.DataFrame, date]:
    key = str(crop).strip().lower()
    config = get_config(key)
    parsed_date = parse_prediction_date(prediction_date)
    required = config["input_features"]
    missing = [name for name in required if name not in values]
    if missing:
        raise ModelInputError("Missing required input(s): " + ", ".join(missing))

    row: dict[str, float] = {}
    for name in required:
        raw = values[name]
        label = FEATURE_LABELS.get(name, name)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise ModelInputError(f"{label} is required.")
        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:
            raise ModelInputError(f"{label} must be numeric.") from exc
        if not math.isfinite(number):
            raise ModelInputError(f"{label} must be a finite number.")
        if number < 0 and name not in SIGNED_FEATURES:
            raise ModelInputError(f"{label} cannot be negative.")
        row[name] = number

    row["dow"] = float(parsed_date.weekday())
    row["dom"] = float(parsed_date.day)
    row["month"] = float(parsed_date.month)
    ordered = config["features"]
    frame = pd.DataFrame([[row[name] for name in ordered]], columns=list(ordered))
    return frame, parsed_date


def predict(crop: str, values: Mapping[str, Any], prediction_date: Any) -> PredictionResult:
    key = str(crop).strip().lower()
    config = get_config(key)
    model = load_model(key)
    frame, parsed_date = build_feature_frame(key, values, prediction_date)

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"X has feature names, but DecisionTreeRegressor was fitted without feature names",
            category=UserWarning,
        )
        predicted = float(model.predict(frame)[0])

    if not math.isfinite(predicted):
        raise RuntimeError("The model returned a non-finite prediction.")

    # This is tree-to-tree variation, not a calibrated prediction interval.
    tree_values = np.asarray(
        [float(tree.predict(frame.to_numpy(dtype=float))[0]) for tree in model.estimators_],
        dtype=float,
    )
    if not np.isfinite(tree_values).all():
        raise RuntimeError("One or more trees returned a non-finite prediction.")

    return PredictionResult(
        crop=key,
        prediction=predicted,
        tree_min=float(tree_values.min()),
        tree_max=float(tree_values.max()),
        tree_std=float(tree_values.std()),
        prediction_date=parsed_date,
        prediction_kind=config["prediction_kind"],
        prediction_label=config["prediction_label"],
        features={name: float(frame.iloc[0][name]) for name in config["features"]},
    )


def get_feature_importance(crop: str) -> pd.DataFrame:
    key = str(crop).strip().lower()
    config = get_config(key)
    model = load_model(key)
    return (
        pd.DataFrame({
            "Feature": config["features"],
            "Importance (%)": np.asarray(model.feature_importances_, dtype=float) * 100.0,
        })
        .sort_values("Importance (%)", ascending=False)
        .reset_index(drop=True)
    )


def get_model_info(crop: str) -> dict[str, Any]:
    key = str(crop).strip().lower()
    config = get_config(key)
    model = load_model(key)
    importance = get_feature_importance(key)
    return {
        "crop": key,
        "display_name": config["display_name"],
        "model_file": config["filename"],
        "model_class": type(model).__name__,
        "n_estimators": len(model.estimators_),
        "n_features": len(config["features"]),
        "features": list(config["features"]),
        "input_features": list(config["input_features"]),
        "prediction_kind": config["prediction_kind"],
        "prediction_label": config["prediction_label"],
        "requires_engineered_features": config["requires_engineered"],
        "feature_importance": importance.to_dict(orient="records"),
    }
