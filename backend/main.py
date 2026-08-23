from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="NAME", version="1.0.0")

# Enable CORS so the React frontend can talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "NAME is live and operational"}

@app.get("/api/forecast")
def get_forecast():
    # Mock data baseline for frontend integration
    # The ML pipeline will replace these values later
    return {
        "status": "success",
        "timestamp": "latest",
        "kp_index": 5.33,
        "geomagnetic_storm_risk": "Moderate",
        "satellite_drag_risk": "Elevated",
        "power_grid_risk": "Nominal"
    }