"""
Experiment script to optimize hyper-parameters and reduce overfitting.
Tries Linear Regression, Ridge, and tuned Random Forest with cross-validation.
"""
import pandas as pd
import numpy as np
import requests
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.metrics import mean_squared_error, r2_score
import joblib

url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
r = requests.get(url, timeout=15)
raw_data = r.json()

# Build DF
if isinstance(raw_data[0], dict):
    df = pd.DataFrame(raw_data)
else:
    df = pd.DataFrame(raw_data[1:], columns=raw_data[0])

df["time_tag"] = pd.to_datetime(df["time_tag"])
df["Kp"] = pd.to_numeric(df["Kp"], errors="coerce")
df = df.dropna(subset=["Kp"]).sort_values("time_tag").reset_index(drop=True)

# Build features
for lag in range(1, 5):
    df[f"kp_lag_{lag}"] = df["Kp"].shift(lag)

df["kp_rolling_mean_3"] = df["Kp"].rolling(3).mean()
df["kp_rolling_max_3"] = df["Kp"].rolling(3).max()
df["kp_trend"] = df["Kp"] - df["Kp"].shift(2)
df["hour"] = df["time_tag"].dt.hour
df["target"] = df["Kp"].shift(-1)
df = df.dropna()

feature_cols = [
    "kp_lag_1", "kp_lag_2", "kp_lag_3", "kp_lag_4",
    "kp_rolling_mean_3", "kp_rolling_max_3", "kp_trend", "hour"
]

X = df[feature_cols]
y = df["target"]

# 1. Time-series cross validation splits
tscv = TimeSeriesSplit(n_splits=5)

models = {
    "LinearRegression": LinearRegression(),
    "Ridge(alpha=1.0)": Ridge(alpha=1.0),
    "Ridge(alpha=10.0)": Ridge(alpha=10.0),
    "RF_baseline": RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
    "RF_shallow": RandomForestRegressor(n_estimators=50, max_depth=3, min_samples_leaf=3, random_state=42),
}

print("=== Cross-Validation Results (RMSE) ===")
for name, model in models.items():
    cv_scores = []
    for train_idx, val_idx in tscv.split(X):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        model.fit(X_tr, y_tr)
        preds = model.predict(X_val)
        rmse = np.sqrt(mean_squared_error(y_val, preds))
        cv_scores.append(rmse)
    
    print(f"  {name:20s} Mean RMSE: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores):.4f})")
