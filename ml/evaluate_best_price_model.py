"""
Evaluation script for best_price_model.joblib on chronological holdout test set.
Saves comprehensive metrics to ml/experiments/best_price_model_evaluation.json.
"""
import json
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.metrics import mean_absolute_error, mean_squared_error

def main():
    csv_path = Path("data/processed/crop_market_observations.csv")
    if not csv_path.exists():
        print(f"Dataset {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    df["market_date"] = pd.to_datetime(df["market_date"])
    df = df.sort_values(["crop", "market_name", "market_date"]).reset_index(drop=True)

    # Reconstruct features matching training pipeline
    df["modal_price"] = pd.to_numeric(df["modal_price"], errors="coerce")
    df["min_price"] = pd.to_numeric(df["min_price"], errors="coerce")
    df["max_price"] = pd.to_numeric(df["max_price"], errors="coerce")
    df["arrivals_in_qtl"] = pd.to_numeric(df["arrivals"], errors="coerce")

    # Group-based shifts
    grp = df.groupby(["crop", "market_name"])
    df["modal_next"] = grp["modal_price"].shift(-1)
    df["modal_prev_1"] = grp["modal_price"].shift(1)
    df["modal_prev_7"] = grp["modal_price"].shift(7)

    df["modal_today"] = df["modal_price"]
    df["spread_ratio"] = (df["max_price"] - df["min_price"]) / df["modal_price"].replace(0, np.nan)
    df["return_1d"] = (df["modal_today"] - df["modal_prev_1"]) / df["modal_prev_1"].replace(0, np.nan)
    df["return_7d"] = (df["modal_today"] - df["modal_prev_7"]) / df["modal_prev_7"].replace(0, np.nan)

    df["modal_roll_std"] = grp["modal_price"].transform(lambda s: s.rolling(7, min_periods=2).std())
    df["arrivals_roll_mean"] = grp["arrivals_in_qtl"].transform(lambda s: s.rolling(7, min_periods=2).mean())
    df["arrival_anomaly"] = df["arrivals_in_qtl"] / df["arrivals_roll_mean"].replace(0, np.nan)

    # Cyclical & calendar features
    dow = df["market_date"].dt.dayofweek
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)
    month = df["market_date"].dt.month
    df["month_sin"] = np.sin(2 * np.pi * month / 12.0)
    df["month_cos"] = np.cos(2 * np.pi * month / 12.0)
    df["day_of_year"] = df["market_date"].dt.dayofyear.astype(float)

    # Categoricals
    df["crop"] = df["crop"].str.upper()
    df["market"] = df["market_name"].str.upper()
    df["district"] = df["district"].fillna("UNKNOWN").str.upper()

    feature_cols = [
        "modal_today", "spread_ratio", "return_1d", "return_7d",
        "arrival_anomaly", "modal_roll_std", "arrivals_roll_mean",
        "dow_sin", "dow_cos", "month_sin", "month_cos", "day_of_year",
        "crop", "market", "district",
    ]

    # Target: relative return
    df["target_return"] = (df["modal_next"] - df["modal_today"]) / df["modal_today"].replace(0, np.nan)

    # Filter valid rows
    valid = df.dropna(subset=feature_cols + ["modal_next", "modal_today"]).copy()
    valid = valid[valid["modal_today"] > 0]
    valid = valid[valid["modal_next"] > 0]

    # Split train < 2026-08-01, test >= 2026-08-01
    split_date = pd.to_datetime("2026-08-01")
    test_df = valid[valid["market_date"] >= split_date].copy()

    # Load model
    model = joblib.load("ml/artifacts/best_price_model.joblib")

    # Predict returns
    pred_returns = model.predict(test_df[feature_cols])
    test_df["pred_return"] = pred_returns
    test_df["pred_price"] = test_df["modal_today"] * (1.0 + test_df["pred_return"])
    test_df["naive_pred"] = test_df["modal_today"]

    # Metrics
    y_true = test_df["modal_next"].values
    y_pred = test_df["pred_price"].values
    y_naive = test_df["naive_pred"].values

    mae_model = float(mean_absolute_error(y_true, y_pred))
    rmse_model = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mape_model = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)

    mae_naive = float(mean_absolute_error(y_true, y_naive))
    rmse_naive = float(np.sqrt(mean_squared_error(y_true, y_naive)))
    mape_naive = float(np.mean(np.abs((y_true - y_naive) / y_true)) * 100)

    # Per crop breakdown
    per_crop = {}
    for crop_name, group in test_df.groupby("crop"):
        yt = group["modal_next"].values
        yp = group["pred_price"].values
        yn = group["naive_pred"].values
        per_crop[crop_name] = {
            "samples": int(len(group)),
            "model_mae": round(float(mean_absolute_error(yt, yp)), 2),
            "naive_mae": round(float(mean_absolute_error(yt, yn)), 2),
            "model_rmse": round(float(np.sqrt(mean_squared_error(yt, yp))), 2),
            "naive_rmse": round(float(np.sqrt(mean_squared_error(yt, yn))), 2),
            "model_mape_pct": round(float(np.mean(np.abs((yt - yp) / yt)) * 100), 2),
            "naive_mape_pct": round(float(np.mean(np.abs((yt - yn) / yt)) * 100), 2),
            "mae_improvement": round(float(mean_absolute_error(yt, yn) - mean_absolute_error(yt, yp)), 2),
        }

    results = {
        "model_artifact": "ml/artifacts/best_price_model.joblib",
        "feature_columns_artifact": "ml/artifacts/feature_columns.joblib",
        "algorithm": "ExtraTreesRegressor (100 estimators, max_depth=10)",
        "preprocessing_pipeline": "ColumnTransformer (StandardScaler on 12 numerics, OneHotEncoder on crop/market/district)",
        "target_variable": "relative_return ((modal_next - modal_today) / modal_today)",
        "prediction_formula": "predicted_price = modal_today * (1.0 + predicted_return)",
        "evaluation_split": {
            "strategy": "Chronological holdout (no lookahead leakage)",
            "split_date": "2026-08-01",
            "test_sample_count": int(len(test_df)),
            "date_range_test": f"{test_df['market_date'].min().strftime('%Y-%m-%d')} to {test_df['market_date'].max().strftime('%Y-%m-%d')}",
        },
        "overall_metrics": {
            "model_mae": round(mae_model, 2),
            "naive_mae": round(mae_naive, 2),
            "model_rmse": round(rmse_model, 2),
            "naive_rmse": round(rmse_naive, 2),
            "model_mape_pct": round(mape_model, 2),
            "naive_mape_pct": round(mape_naive, 2),
            "overall_improvement_mae": round(mae_naive - mae_model, 2),
        },
        "commodity_breakdown": per_crop,
    }

    out_file = Path("ml/experiments/best_price_model_evaluation.json")
    out_file.write_text(json.dumps(results, indent=2))
    print(f"Evaluation report written to {out_file}")
    print(json.dumps(results["overall_metrics"], indent=2))

if __name__ == "__main__":
    main()
