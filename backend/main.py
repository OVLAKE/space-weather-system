from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import List, Dict, Any

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

NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"

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

@app.get("/")
def root():
    return {"status": "online", "message": "Space Weather API is operational"}

import pandas as pd
import requests

@app.get("/api/kp-live")
def get_live_kp_data() -> Dict[str, Any]:
    """Fetches real-time Kp-index data directly from NOAA SWPC."""
    try:
        response = requests.get(NOAA_KP_URL)
        response.raise_for_status()
        raw_data = response.json()

        # Convert to DataFrame (skip the header row)
        df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
        
        if df.empty:
             raise ValueError("NOAA returned empty data arrays.")
             
        # Bulletproof: Dynamically grab the exact column names NOAA uses
        time_col = df.columns[0]
        kp_col = df.columns[1]
             
        # Extract the latest entry
        latest_entry = df.iloc[-1]
        time_tag = latest_entry[time_col]
        kp_val = float(latest_entry[kp_col])

        risk_info = evaluate_kp_risk(kp_val)

        # Prepare recent history
        recent_history = []
        for _, row in df.tail(10).iterrows():
            recent_history.append({"timestamp": row[time_col], "kp": float(row[kp_col])})

        return {
            "timestamp": time_tag,
            "current_kp": kp_val,
            "risk_assessment": risk_info,
            "recent_history": recent_history
        }
    except requests.exceptions.RequestException as exc:
         raise HTTPException(status_code=502, detail=f"Failed to fetch NOAA data: {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal processing error: {repr(exc)}")