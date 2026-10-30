"""Prediction adapter for the four supplied crop RandomForest models.

Feature engineering for the 17-feature delta estimators is inferred from the
feature names because their training notebook/preprocessing code was not part
of the supplied files. Results are therefore explicitly marked experimental.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
import math
import warnings

import numpy as np
import pandas as pd
import joblib

from cropmandi.db.models import CropMarketObservation
from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "ml" / "artifacts"
COMMON = [
    "modal_today", "modal_lag1", "modal_lag2", "modal_lag3", "modal_lag7",
    "modal_roll_mean", "modal_roll_std", "arrivals_lag1", "arrivals_roll_mean", "spread_lag1",
]
CALENDAR = ["dow", "dom", "month"]
ENGINEERED = ["price_dev_roll", "momentum_1d", "momentum_7d", "arrivals_log"]
MODEL_CONFIG = {
    "tomato": {
        "name": "Tomato", "file": "tomato_price_model.pkl", "kind": "price_level",
        "features": COMMON + CALENDAR, "requires_engineered": False,
    },
    "maize": {
        "name": "Maize", "file": "maize_delta_rf_model.pkl", "kind": "delta",
        "features": COMMON + CALENDAR + ENGINEERED, "requires_engineered": True,
    },
    "paddy": {
        "name": "Paddy", "file": "paddy_delta_rf_model.pkl", "kind": "delta",
        "features": COMMON + CALENDAR + ENGINEERED, "requires_engineered": True,
    },
    "potato": {
        "name": "Potato", "file": "potato_delta_rf_model.pkl", "kind": "delta",
        "features": COMMON + CALENDAR + ENGINEERED, "requires_engineered": True,
    },
}
FEATURE_ASSUMPTIONS = {
    "history_lags": "Lag values are taken from the previous 1, 2, 3 and 7 available market observations, not calendar days.",
    "rolling_window": "Rolling mean and standard deviation use the latest 7 available observations including the latest observation.",
    "spread_lag1": "Previous observation's max_price minus min_price; 0 when either endpoint was absent.",
    "price_dev_roll": "Inferred as modal_today - modal_roll_mean.",
    "momentum_1d": "Inferred as modal_today - modal_lag1.",
    "momentum_7d": "Inferred as modal_today - modal_lag7.",
    "arrivals_log": "Inferred as natural log of (1 + arrivals_lag1).",
    "target_semantics": "The pickle does not contain the target construction or forecast horizon; delta-to-price is shown only as an indicative derivation.",
}


class CropModelError(ValueError):
    pass


@lru_cache(maxsize=4)
def load_model(crop: str):
    crop = crop.lower()
    if crop not in MODEL_CONFIG:
        raise CropModelError(f"Unsupported crop model: {crop}")
    path = MODEL_DIR / MODEL_CONFIG[crop]["file"]
    if not path.exists():
        raise FileNotFoundError(f"Missing model artifact: {path}")
    # The supplied models were serialized with sklearn 1.7.2. Keep the project
    # pinned to that version; warnings are suppressed only for local testing.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"Trying to unpickle estimator .* from version .*", category=UserWarning)
        model = joblib.load(path)
    expected = MODEL_CONFIG[crop]["features"]
    if getattr(model, "n_features_in_", None) != len(expected):
        raise RuntimeError(f"{crop} model schema mismatch: expected {len(expected)} features")
    names = list(getattr(model, "feature_names_in_", []))
    if names and names != expected:
        raise RuntimeError(f"{crop} model feature order mismatch")
    if not callable(getattr(model, "predict", None)):
        raise RuntimeError(f"{crop} model does not expose predict()")
    return model


def _number(value) -> float:
    if value is None:
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def model_registry(session: Session) -> dict:
    from sqlalchemy import func
    results = []
    for crop, config in MODEL_CONFIG.items():
        row_count = session.scalar(select(func.count()).select_from(CropMarketObservation).where(CropMarketObservation.crop_code == crop)) or 0
        market_count = session.scalar(select(func.count(func.distinct(CropMarketObservation.market_name))).where(CropMarketObservation.crop_code == crop)) or 0
        try:
            model = load_model(crop)
            model_status = "READY"
            feature_importance = sorted(
                [{"feature": name, "importance_pct": round(float(value) * 100, 3)} for name, value in zip(config["features"], model.feature_importances_)],
                key=lambda x: -x["importance_pct"],
            )[:8]
        except Exception as exc:
            model_status = f"ERROR: {exc}"
            feature_importance = []
        results.append({
            "crop": crop, "name": config["name"], "model_file": config["file"],
            "prediction_kind": config["kind"], "feature_count": len(config["features"]),
            "model_status": model_status, "observation_count": int(row_count),
            "market_count": int(market_count), "feature_importance_top": feature_importance,
            "evaluation_status": "NOT_VALIDATED_AGAINST_HELD_OUT_ACTUALS",
        })
    return {"models": results, "feature_assumptions": FEATURE_ASSUMPTIONS}


def crop_options(session: Session, crop: str) -> dict:
    from sqlalchemy import func
    crop = crop.lower()
    if crop not in MODEL_CONFIG:
        raise CropModelError(f"Unsupported crop: {crop}")
    grouped = session.execute(
        select(
            CropMarketObservation.market_name,
            CropMarketObservation.district,
            CropMarketObservation.variety,
            CropMarketObservation.grade,
            CropMarketObservation.unit,
            func.count(CropMarketObservation.id).label("observations"),
        ).where(CropMarketObservation.crop_code == crop).group_by(
            CropMarketObservation.market_name, CropMarketObservation.district,
            CropMarketObservation.variety, CropMarketObservation.grade, CropMarketObservation.unit,
        )
    ).all()
    market_series: dict[tuple[str, str], list[dict]] = {}
    for row in grouped:
        market_series.setdefault((row.market_name, row.district), []).append({
            "variety": row.variety, "grade": row.grade, "unit": row.unit,
            "observation_count": int(row.observations),
            "prediction_ready": int(row.observations) >= 8,
        })
    markets = sorted(
        market_series,
        key=lambda key: (-max((x["observation_count"] for x in market_series[key]), default=0), key[1].casefold(), key[0].casefold()),
    )
    all_series = [s for values in market_series.values() for s in values]
    varieties = sorted({r["variety"] for r in all_series if r["variety"]})
    grades = sorted({r["grade"] for r in all_series if r["grade"]})
    units = sorted({r["unit"] for r in all_series if r["unit"]})
    count = session.scalar(select(func.count()).select_from(CropMarketObservation).where(CropMarketObservation.crop_code == crop)) or 0
    return {
        "crop": crop,
        "markets": [
            {"market_name": name, "district": district,
             "series_options": sorted(market_series[(name, district)], key=lambda x: (-x["observation_count"], x["variety"].casefold(), x["grade"].casefold()))}
            for name, district in markets
        ],
        "varieties": varieties,
        "grades": grades,
        "units": units,
        "total_observations": int(count),
    }


def _select_series(session: Session, crop: str, market: str, district: str | None, variety: str, grade: str, limit: int = 40):
    stmt = select(CropMarketObservation).where(
        CropMarketObservation.crop_code == crop,
        CropMarketObservation.market_name == market,
        CropMarketObservation.variety == variety,
        CropMarketObservation.grade == grade,
    )
    if district:
        stmt = stmt.where(CropMarketObservation.district == district)
    stmt = stmt.order_by(CropMarketObservation.market_date.desc(), CropMarketObservation.id.desc()).limit(limit)
    return list(reversed(session.scalars(stmt).all()))


def build_features(history: list[CropMarketObservation], crop: str, forecast_date: date | None = None) -> tuple[pd.DataFrame, dict]:
    config = MODEL_CONFIG[crop]
    if len(history) < 8:
        raise CropModelError(f"At least 8 dated market observations are needed; found {len(history)}.")
    latest = history[-1]
    previous = history[-2]
    p = [_number(row.modal_price) for row in history]
    a = [_number(row.arrivals) for row in history]
    window_prices = p[-7:]
    window_arrivals = a[-7:]
    modal_today = p[-1]
    modal_lag1, modal_lag2, modal_lag3, modal_lag7 = p[-2], p[-3], p[-4], p[-8]
    modal_roll_mean = float(np.mean(window_prices))
    modal_roll_std = float(np.std(window_prices, ddof=0))
    arrivals_lag1 = a[-2]
    arrivals_roll_mean = float(np.mean(window_arrivals))
    spread_lag1 = max(_number(previous.max_price) - _number(previous.min_price), 0.0)
    prediction_date = forecast_date or (latest.market_date + timedelta(days=1))
    features = {
        "modal_today": modal_today,
        "modal_lag1": modal_lag1,
        "modal_lag2": modal_lag2,
        "modal_lag3": modal_lag3,
        "modal_lag7": modal_lag7,
        "modal_roll_mean": modal_roll_mean,
        "modal_roll_std": modal_roll_std,
        "arrivals_lag1": arrivals_lag1,
        "arrivals_roll_mean": arrivals_roll_mean,
        "spread_lag1": spread_lag1,
        "dow": float(prediction_date.weekday()),
        "dom": float(prediction_date.day),
        "month": float(prediction_date.month),
    }
    if config["requires_engineered"]:
        features.update({
            "price_dev_roll": modal_today - modal_roll_mean,
            "momentum_1d": modal_today - modal_lag1,
            "momentum_7d": modal_today - modal_lag7,
            "arrivals_log": float(np.log1p(max(arrivals_lag1, 0.0))),
        })
    X = pd.DataFrame([[features[name] for name in config["features"]]], columns=config["features"])
    metadata = {
        "latest_observation_date": latest.market_date.isoformat(),
        "prediction_date": prediction_date.isoformat(),
        "base_modal_price": modal_today,
        "unit": latest.unit,
        "history_observations_used": len(history),
        "features": features,
        "feature_engineering_status": "INFERRED_FROM_FEATURE_NAMES" if config["requires_engineered"] else "RECONSTRUCTED_FROM_MARKET_HISTORY",
    }
    return X, metadata


def predict_from_history(session: Session, crop: str, market: str, district: str | None, variety: str, grade: str, forecast_date: date | None = None) -> dict:
    crop = crop.lower()
    if crop not in MODEL_CONFIG:
        raise CropModelError(f"Unsupported crop model: {crop}")
    history = _select_series(session, crop, market, district, variety, grade, limit=40)
    if not history:
        raise CropModelError("No matching market history was found for this crop/market/variety/grade.")
    X, meta = build_features(history, crop, forecast_date)
    model = load_model(crop)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        raw_prediction = float(model.predict(X)[0])
    if not math.isfinite(raw_prediction):
        raise RuntimeError("Model produced a non-finite prediction.")
    result = {
        "crop": crop,
        "market_name": market,
        "district": district or history[-1].district,
        "variety": variety,
        "grade": grade,
        "prediction_date": meta["prediction_date"],
        "latest_observation_date": meta["latest_observation_date"],
        "base_modal_price": round(meta["base_modal_price"], 2),
        "unit": meta["unit"],
        "raw_model_output": round(raw_prediction, 4),
        "prediction_kind": MODEL_CONFIG[crop]["kind"],
        "history_observations_used": meta["history_observations_used"],
        "features_used": meta["features"],
        "feature_engineering_status": meta["feature_engineering_status"],
        "feature_assumptions": FEATURE_ASSUMPTIONS if crop != "tomato" else {k: v for k, v in FEATURE_ASSUMPTIONS.items() if k in ("history_lags", "rolling_window", "spread_lag1", "target_semantics")},
        "model_accuracy_status": "NOT_VALIDATED_AGAINST_HELD_OUT_ACTUALS",
        "data_status": "USER_SUPPLIED_AGMARKNET_EXPORT_UNVERIFIED",
    }
    if crop == "tomato":
        result.update({
            "predicted_modal_price": round(raw_prediction, 2),
            "display_label": "Model modal-price output (training target horizon not included in pickle)",
        })
    else:
        result.update({
            "predicted_delta": round(raw_prediction, 2),
            "indicative_modal_price_if_delta_is_next_session_change": round(meta["base_modal_price"] + raw_prediction, 2),
            "display_label": "Experimental model delta; added-to-price value is an assumption, not a verified target definition",
        })
    return result


def crop_rankings(session: Session, crop: str, variety: str | None, grade: str | None, limit: int = 10) -> dict:
    stmt = select(CropMarketObservation).where(CropMarketObservation.crop_code == crop)
    records = session.scalars(stmt.order_by(CropMarketObservation.market_date.desc())).all()
    series_pairs = sorted({(r.variety, r.grade) for r in records}, key=lambda x: (x[0].casefold(), x[1].casefold()))
    series_options = [
        {"value": __import__("json").dumps([v, g], ensure_ascii=False), "label": f"{v} · {g}"}
        for v, g in series_pairs
    ]
    if variety is None and grade is None and series_pairs:
        variety, grade = series_pairs[0]
    if variety is not None:
        records = [r for r in records if r.variety == variety]
    if grade is not None:
        records = [r for r in records if r.grade == grade]
    latest = {}
    for row in records:
        key = (row.market_name, row.district)
        if key not in latest or row.market_date > latest[key].market_date:
            latest[key] = row
    rankings = sorted(latest.values(), key=lambda r: (-float(r.modal_price), -r.market_date.toordinal(), r.market_name.casefold()))
    selected_series = __import__("json").dumps([variety, grade], ensure_ascii=False) if variety is not None and grade is not None else None
    return {
        "commodity": crop,
        "series_options": series_options,
        "selected_series": selected_series,
        "variety_options": sorted({r.variety for r in records}),
        "grade_options": sorted({r.grade for r in records}),
        "selected_variety": variety,
        "selected_grade": grade,
        "rankings": [
            {"rank": i + 1, "market_name": r.market_name, "locations": [r.district] if r.district else [],
             "price": float(r.modal_price), "unit": r.unit, "date": r.market_date.isoformat(),
             "freshness_status": "HISTORICAL" if (date.today() - r.market_date).days > 30 else "RECENT",
             "age_days": max((date.today() - r.market_date).days, 0),
             "data_status": r.data_status, "official": False}
            for i, r in enumerate(rankings[:limit])
        ],
        "count": min(len(rankings), limit),
        "total_markets": len(rankings),
        "as_of": max((r.market_date.isoformat() for r in latest.values()), default=None),
        "unit": (rankings[0].unit if rankings else None),
        "source": "User-supplied AGMARKNET date-wise XLS HTML exports",
        "provenance": "User-supplied AGMARKNET report exports; source and completeness not independently verified.",
        "data_status": "USER_SUPPLIED_AGMARKNET_EXPORT_UNVERIFIED" if records else "NO_DATA_AVAILABLE",
        "official": False,
        "ranking_method": "Latest stored modal observation per market for the selected variety/grade, sorted high-to-low. Observation dates may differ between markets.",
    }
