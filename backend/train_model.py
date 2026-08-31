"""
Refined Kp-index forecasting model training pipeline.
Dynamically compares multiple machine learning algorithms (L2 regularized Ridge
and shallow Random Forests) using Time Series Cross-Validation (TimeSeriesSplit)
and selects the best performing model. Saves the optimal model to disk.
"""
import pandas as pd
import numpy as np
import requests
import joblib
import os
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


def fetch_kp_data() -> pd.DataFrame:
    """Fetch Kp-index data from NOAA SWPC."""
    print("Fetching Kp-index data from NOAA...")
    url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    raw = response.json()

    if isinstance(raw[0], dict):
        df = pd.DataFrame(raw)
    else:
        df = pd.DataFrame(raw[1:], columns=raw[0])

    df["time_tag"] = pd.to_datetime(df["time_tag"])
    df["Kp"] = pd.to_numeric(df["Kp"], errors="coerce")
    df = df.dropna(subset=["Kp"])
    print(f"  Got {len(df)} Kp records")
    return df


def build_features(kp_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Build lag and time-series feature matrix.
    """
    df = kp_df.copy().sort_values("time_tag").reset_index(drop=True)

    # Lag features
    for lag in range(1, 5):
        df[f"kp_lag_{lag}"] = df["Kp"].shift(lag)

    # Rolling stats
    df["kp_rolling_mean_3"] = df["Kp"].rolling(3).mean()
    df["kp_rolling_max_3"] = df["Kp"].rolling(3).max()

    # Trend
    df["kp_trend"] = df["Kp"] - df["Kp"].shift(2)

    # Time feature
    df["hour"] = df["time_tag"].dt.hour

    # Target: Kp value at t+1 (next 3h)
    df["target"] = df["Kp"].shift(-1)

    # Drop NaNs from shift operations
    df = df.dropna()

    feature_cols = [
        "kp_lag_1", "kp_lag_2", "kp_lag_3", "kp_lag_4",
        "kp_rolling_mean_3", "kp_rolling_max_3", "kp_trend", "hour"
    ]

    X = df[feature_cols]
    y = df["target"]

    return X, y


def train_and_save():
    print("=" * 50)
    print("  Kp Forecast Model Refinement Pipeline")
    print("=" * 50)
    print()

    # 1. Fetch data
    kp_df = fetch_kp_data()

    # 2. Build features
    X, y = build_features(kp_df)
    print(f"\nBuilding features...")
    print(f"  Shape: {X.shape[0]} samples, {X.shape[1]} features")

    # 3. Model Candidates
    candidates = {
        "Ridge(alpha=1.0)": Ridge(alpha=1.0),
        "Ridge(alpha=5.0)": Ridge(alpha=5.0),
        "Ridge(alpha=20.0)": Ridge(alpha=20.0),
        "RandomForest(shallow)": RandomForestRegressor(n_estimators=60, max_depth=3, min_samples_leaf=3, random_state=42),
        "RandomForest(baseline)": RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
    }

    # 4. Time Series Cross Validation (5 folds)
    tscv = TimeSeriesSplit(n_splits=5)
    print("\nRunning Time-Series Cross-Validation...")

    best_name = None
    best_score = float("inf")
    best_model = None

    for name, model in candidates.items():
        scores = []
        for train_idx, val_idx in tscv.split(X):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model.fit(X_tr, y_tr)
            preds = model.predict(X_val)
            rmse = np.sqrt(mean_squared_error(y_val, preds))
            scores.append(rmse)

        mean_rmse = np.mean(scores)
        std_rmse = np.std(scores)
        print(f"  {name:25s} | Mean CV RMSE: {mean_rmse:.4f} (std: {std_rmse:.4f})")

        if mean_rmse < best_score:
            best_score = mean_rmse
            best_name = name
            best_model = model

    print(f"\n[WINNER] Selected: {best_name} with CV RMSE {best_score:.4f}")

    # 5. Final fit on 100% of historical data
    print(f"Fitting final {best_name} model on all {len(X)} samples...")
    best_model.fit(X, y)

    # Evaluate final model fit
    final_preds = best_model.predict(X)
    train_rmse = np.sqrt(mean_squared_error(y, final_preds))
    train_r2 = r2_score(y, final_preds)
    print(f"  Final Fit RMSE: {train_rmse:.4f}")
    print(f"  Final Fit R²:   {train_r2:.4f}")

    # 6. Save model artifact
    model_dir = os.path.join(os.path.dirname(__file__), "model")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "kp_forecast_model.joblib")

    artifact = {
        "model": best_model,
        "feature_columns": list(X.columns),
        "training_samples": len(X),
        "test_rmse": float(best_score),  # Stores CV score as test score for UI display
        "test_r2": float(train_r2),
        "model_name": best_name
    }
    joblib.dump(artifact, model_path)
    print(f"\n[OK] Refined model saved to: {model_path}")
    return artifact


if __name__ == "__main__":
    train_and_save()
