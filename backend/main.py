from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import requests
import logging
import joblib
import os
from antigravity_core import AntigravitySuite
logger = logging.getLogger("space-weather")

app = FastAPI(
    title="Space Weather Decision Support API",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust to frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
NOAA_PLASMA_URL = "https://services.swpc.noaa.gov/products/geospace/propagated-solar-wind-1-hour.json"


# ---------------------------------------------------------------------------
# In-memory cache: stores the last successful response for each endpoint.
# A warning system must ALWAYS return data — if NOAA is down, we serve the
# last known good reading with a "stale" flag so the frontend can warn the
# operator that the data is not live.
# ---------------------------------------------------------------------------
_cache: Dict[str, Dict[str, Any]] = {}


def _cache_set(key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Store a successful response in cache and mark it as live."""
    data["data_status"] = "live"
    data["fetched_at"] = datetime.now(timezone.utc).isoformat()
    _cache[key] = data
    return data


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    """Return the last cached response marked as stale, or None."""
    if key not in _cache:
        return None
    stale = dict(_cache[key])
    stale["data_status"] = "stale"
    stale["stale_reason"] = "NOAA data source temporarily unavailable; showing last known data."
    return stale


def safe_float(value, default=None) -> float | None:
    """Safely convert a value to float, returning default on failure."""
    try:
        if value is None:
            return default
        result = float(value)
        if pd.isna(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


def format_utc_timestamp(ts_str: str) -> str:
    """Ensure the timestamp string is parsed and returned with a UTC timezone suffix."""
    try:
        dt = pd.to_datetime(ts_str)
        if dt.tzinfo is None:
            dt = dt.tz_localize('UTC')
        return dt.isoformat()
    except Exception:
        if not ts_str.endswith('Z') and '+' not in ts_str:
            return ts_str + 'Z'
        return ts_str


def evaluate_kp_risk(kp_value: float) -> Dict[str, str]:
    """Calculates operational impact level based on Kp index."""
    if kp_value >= 7:
        return {"level": "CRITICAL", "action": "Reroute polar flights / grid mitigation"}
    elif kp_value >= 5:
        return {"level": "WARNING", "action": "Monitor HF radio / satellite degradation"}
    elif kp_value >= 4:
        return {"level": "UNSETTLED", "action": "Elevated auroral activity"}
    else:
        return {"level": "NORMAL", "action": "Nominal operations"}


def evaluate_wind_risk(speed: float) -> Dict[str, str]:
    """Calculates operational risk based on Solar Wind speed (km/s)."""
    if speed >= 800:
        return {"level": "CRITICAL", "action": "Extreme solar wind detected; high storm probability"}
    elif speed >= 500:
        return {"level": "WARNING", "action": "Elevated solar wind; monitor for geomagnetic disruption"}
    else:
        return {"level": "NORMAL", "action": "Nominal solar wind"}


@app.get("/")
def root():
    return {"status": "online", "message": "Space Weather API is operational"}


@app.get("/api/kp-live")
def get_live_kp_data() -> Dict[str, Any]:
    """Fetches real-time Kp-index data directly from NOAA SWPC.
    
    Always returns data: live when NOAA is reachable, or the last
    cached reading (marked stale) when NOAA is unavailable.
    """
    try:
        response = requests.get(NOAA_KP_URL, timeout=15)
        response.raise_for_status()
        raw_data = response.json()

        if not raw_data or len(raw_data) < 2:
            raise ValueError("NOAA returned insufficient data.")

        # Build DataFrame — handles both list-header and dict-row formats
        header = raw_data[0]
        if isinstance(header, dict):
            df = pd.DataFrame(raw_data)
        else:
            df = pd.DataFrame(raw_data[1:], columns=header)

        # Validate expected columns
        if "time_tag" not in df.columns or "Kp" not in df.columns:
            raise ValueError(f"Expected 'time_tag' and 'Kp' columns, got: {list(df.columns)}")

        # Filter to rows with valid Kp values
        df["Kp_parsed"] = df["Kp"].apply(safe_float)
        df = df.dropna(subset=["Kp_parsed"])

        if df.empty:
            raise ValueError("No valid Kp data rows after filtering.")

        # Extract the latest entry
        latest_entry = df.iloc[-1]
        time_tag = format_utc_timestamp(str(latest_entry["time_tag"]))
        kp_val = latest_entry["Kp_parsed"]

        risk_info = evaluate_kp_risk(kp_val)

        # Prepare recent history
        recent_history = []
        for _, row in df.tail(10).iterrows():
            recent_history.append({
                "timestamp": format_utc_timestamp(str(row["time_tag"])),
                "kp": row["Kp_parsed"]
            })

        result = {
            "timestamp": time_tag,
            "current_kp": kp_val,
            "risk_assessment": risk_info,
            "recent_history": recent_history
        }
        return _cache_set("kp", result)

    except Exception as exc:
        logger.warning("Kp fetch failed (%s), falling back to cache.", exc)
        cached = _cache_get("kp")
        if cached is not None:
            return cached
        # No cache yet (first request ever failed) — return safe defaults
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_kp": 0.0,
            "risk_assessment": evaluate_kp_risk(0.0),
            "recent_history": [],
            "data_status": "unavailable",
            "stale_reason": "NOAA data source unreachable and no cached data available yet."
        }


@app.get("/api/solar-wind-live")
def get_live_solar_wind() -> Dict[str, Any]:
    """Fetches real-time Solar Wind plasma data directly from NOAA SWPC.
    
    Always returns data: live when NOAA is reachable, or the last
    cached reading (marked stale) when NOAA is unavailable.
    """
    try:
        response = requests.get(NOAA_PLASMA_URL, timeout=15)
        response.raise_for_status()
        raw_data = response.json()

        if not raw_data or len(raw_data) < 2:
            raise ValueError("NOAA returned insufficient data.")

        # Build DataFrame — handles both list-header and dict-row formats
        header = raw_data[0]
        if isinstance(header, dict):
            df = pd.DataFrame(raw_data)
        else:
            df = pd.DataFrame(raw_data[1:], columns=header)

        # Validate expected columns
        for col in ["time_tag", "speed", "density"]:
            if col not in df.columns:
                raise ValueError(f"Missing expected column '{col}'. Got: {list(df.columns)}")

        # Safely parse speed and density, then drop rows that failed
        df["speed_parsed"] = df["speed"].apply(safe_float)
        df["density_parsed"] = df["density"].apply(safe_float)
        df = df.dropna(subset=["speed_parsed", "density_parsed"])

        if df.empty:
            raise ValueError("No valid solar wind data rows after filtering.")

        # Extract the latest valid entry
        latest_entry = df.iloc[-1]
        time_tag = str(latest_entry["time_tag"])
        wind_speed = latest_entry["speed_parsed"]
        wind_density = latest_entry["density_parsed"]

        risk_info = evaluate_wind_risk(wind_speed)

        # Prepare recent history
        recent_history = []
        for _, row in df.tail(10).iterrows():
            recent_history.append({
                "timestamp": str(row["time_tag"]),
                "speed": row["speed_parsed"],
                "density": row["density_parsed"]
            })

        result = {
            "timestamp": time_tag,
            "current_speed": wind_speed,
            "current_density": wind_density,
            "risk_assessment": risk_info,
            "recent_history": recent_history
        }
        return _cache_set("solar_wind", result)

    except Exception as exc:
        logger.warning("Solar wind fetch failed (%s), falling back to cache.", exc)
        cached = _cache_get("solar_wind")
        if cached is not None:
            return cached
        # No cache yet — return safe defaults
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_speed": 0.0,
            "current_density": 0.0,
            "risk_assessment": evaluate_wind_risk(0.0),
            "recent_history": [],
            "data_status": "unavailable",
            "stale_reason": "NOAA data source unreachable and no cached data available yet."
        }


# --- ML FORECAST ENDPOINT ---

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model", "kp_forecast_model.joblib")
_model_artifact = None

def get_model():
    global _model_artifact
    if _model_artifact is None:
        if os.path.exists(MODEL_PATH):
            try:
                _model_artifact = joblib.load(MODEL_PATH)
            except Exception as e:
                logger.error("Failed to load ML model: %s", e)
        else:
            logger.warning("Model file not found at %s. Predictions will use fallback.", MODEL_PATH)
    return _model_artifact

@app.get("/api/kp-forecast")
def get_kp_forecast() -> Dict[str, Any]:
    """Forecasts the next 3-hour Kp index using the trained Random Forest model.
    
    Always returns data: live forecast when NOAA is reachable and model is trained,
    or the last cached forecast (marked stale) when NOAA is unavailable.
    """
    try:
        response = requests.get(NOAA_KP_URL, timeout=15)
        response.raise_for_status()
        raw_data = response.json()

        if not raw_data or len(raw_data) < 2:
            raise ValueError("NOAA returned insufficient data.")

        # Build DataFrame
        header = raw_data[0]
        if isinstance(header, dict):
            df = pd.DataFrame(raw_data)
        else:
            df = pd.DataFrame(raw_data[1:], columns=header)

        # Validate columns
        if "time_tag" not in df.columns or "Kp" not in df.columns:
            raise ValueError(f"Expected 'time_tag' and 'Kp' columns, got: {list(df.columns)}")

        # Filter valid Kp
        df["Kp_parsed"] = df["Kp"].apply(safe_float)
        df = df.dropna(subset=["Kp_parsed"])

        if len(df) < 4:
            raise ValueError("Insufficient data history (need at least 4 readings) to construct lag features.")

        # Sort and take latest 4
        df = df.sort_values("time_tag").reset_index(drop=True)
        latest_4 = df.tail(4).reset_index(drop=True)
        
        kp_t = latest_4.loc[3, "Kp_parsed"]
        kp_t_1 = latest_4.loc[2, "Kp_parsed"]
        kp_t_2 = latest_4.loc[1, "Kp_parsed"]
        kp_t_3 = latest_4.loc[0, "Kp_parsed"]
        
        kp_rolling_mean_3 = (kp_t + kp_t_1 + kp_t_2) / 3.0
        kp_rolling_max_3 = max(kp_t, kp_t_1, kp_t_2)
        kp_trend = kp_t - kp_t_2
        
        time_tag_t = pd.to_datetime(latest_4.loc[3, "time_tag"])
        if time_tag_t.tzinfo is None:
            time_tag_t = time_tag_t.tz_localize('UTC')
        hour = time_tag_t.hour
        
        features = {
            "kp_lag_1": kp_t,
            "kp_lag_2": kp_t_1,
            "kp_lag_3": kp_t_2,
            "kp_lag_4": kp_t_3,
            "kp_rolling_mean_3": kp_rolling_mean_3,
            "kp_rolling_max_3": kp_rolling_max_3,
            "kp_trend": kp_trend,
            "hour": hour
        }
        
        # Prepare recursive forecasts (3 steps: 3h, 6h, 9h)
        forecast_list = []
        artifact = get_model()
        
        current_time = time_tag_t
        curr_kp = kp_t
        curr_kp_1 = kp_t_1
        curr_kp_2 = kp_t_2
        curr_kp_3 = kp_t_3
        
        for step in range(1, 4):
            roll_mean = (curr_kp + curr_kp_1 + curr_kp_2) / 3.0
            roll_max = max(curr_kp, curr_kp_1, curr_kp_2)
            trend = curr_kp - curr_kp_1
            step_hour = current_time.hour
            
            features = {
                "kp_lag_1": curr_kp,
                "kp_lag_2": curr_kp_1,
                "kp_lag_3": curr_kp_2,
                "kp_lag_4": curr_kp_3,
                "kp_rolling_mean_3": roll_mean,
                "kp_rolling_max_3": roll_max,
                "kp_trend": trend,
                "hour": step_hour
            }
            
            if artifact is not None:
                model = artifact["model"]
                feature_cols = artifact["feature_columns"]
                X_pred = pd.DataFrame([features])[feature_cols]
                pred_val = float(model.predict(X_pred)[0])
            else:
                pred_val = curr_kp
                
            pred_val = max(0.0, min(9.0, round(pred_val, 2)))
            
            # Step time forward by 3 hours
            current_time = current_time + pd.Timedelta(hours=3)
            risk = evaluate_kp_risk(pred_val)
            
            forecast_list.append({
                "forecast_time": current_time.isoformat(),
                "forecasted_kp": pred_val,
                "risk_assessment": risk
            })
            
            # Recursive update
            curr_kp_3 = curr_kp_2
            curr_kp_2 = curr_kp_1
            curr_kp_1 = curr_kp
            curr_kp = pred_val

        if artifact is not None:
            model_info = {
                "model_name": artifact.get("model_name", "Ridge(alpha=5.0)"),
                "training_samples": artifact.get("training_samples"),
                "test_rmse": artifact.get("test_rmse"),
                "test_r2": artifact.get("test_r2")
            }
        else:
            model_info = {"warning": "Model not found; using persistence fallback"}

        result = {
            "observation_time": time_tag_t.isoformat(),
            "current_kp": kp_t,
            "forecasts": forecast_list,
            "model_info": model_info
        }
        return _cache_set("kp_forecast", result)

    except Exception as exc:
        logger.warning("Kp forecast fetch failed (%s), falling back to cache.", exc)
        cached = _cache_get("kp_forecast")
        if cached is not None:
            return cached
        # No cache yet — return safe defaults
        now = datetime.now(timezone.utc)
        return {
            "observation_time": now.isoformat(),
            "current_kp": 0.0,
            "forecasts": [
                {
                    "forecast_time": (now + pd.Timedelta(hours=3 * i)).isoformat(),
                    "forecasted_kp": 0.0,
                    "risk_assessment": evaluate_kp_risk(0.0)
                } for i in range(1, 4)
            ],
            "model_info": {"error": "NOAA unreachable and model/cache unavailable"},
            "data_status": "unavailable",
            "stale_reason": "NOAA data source unreachable and no cached data available yet."
        }

@app.get("/api/antigravity-core")
async def get_antigravity_core():
    """
    Instantiates the AntigravitySuite, fetches the latest live global inputs, 
    and returns the massive simulated physics payload (NavIC, Grid, Aditya-L1, Orbits).
    """
    try:
        # Fetch live inputs (this relies on the cache if endpoints already ran, or hits the source directly)
        kp_res = await get_kp_live()
        kp = float(kp_res.get("current_kp", 0.0))
        
        sw_res = await get_solar_wind_live()
        speed = float(sw_res.get("current_speed", 400.0))
        density = float(sw_res.get("current_density", 5.0))
    except Exception as e:
        logger.warning(f"Core fallback: {e}")
        kp = 0.0
        speed = 400.0
        density = 5.0
        
    suite = AntigravitySuite()
    return suite.run_full_diagnostics(kp=kp, speed=speed, density=density)