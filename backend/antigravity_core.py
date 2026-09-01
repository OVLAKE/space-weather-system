import json
import math
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

# ==============================================================================
# SUBSYSTEM 4: ADVANCED PREDICTIVE CORE (THE "HOLY GRAIL")
# ==============================================================================
class AdityaL1Predictor:
    """
    Ingests live telemetry from ISRO's Aditya-L1 (ASPEX/PAPA instruments).
    Predicts Interplanetary Magnetic Field (IMF) Bz orientation and CME arrival times.
    """
    L1_DISTANCE_KM = 1.5e6  # Distance from Earth to L1 Lagrange point

    def __init__(self):
        self.ml_pipeline_initialized = True  # Placeholder for LSTM/PINN model load

    def generate_mock_telemetry(self, base_speed: float, base_density: float) -> Dict[str, Any]:
        """Simulates raw telemetry from ASPEX (Solar wind ions) and PAPA (Electrons)."""
        return {
            "aspex_alpha_proton_ratio": round(random.uniform(0.01, 0.1) * (base_speed / 400), 4),
            "papa_electron_temp_ev": round(random.uniform(5, 20) * (base_density / 5), 2),
            "sw_velocity_x_km_s": base_speed + random.uniform(-10, 10),
            "sw_velocity_y_km_s": random.uniform(-50, 50),
            "sw_velocity_z_km_s": random.uniform(-50, 50)
        }

    def predict_cme_and_imf(self, kp: float, speed: float, density: float) -> Dict[str, Any]:
        """
        Uses physics-informed heuristics (placeholder for neural net) to predict 
        southward IMF (Bz) and the Earth-arrival time buffer.
        """
        telemetry = self.generate_mock_telemetry(speed, density)
        
        # Calculate Time to Earth (Distance / Speed)
        # e.g., 1,500,000 km / 600 km/s = 2500 seconds (~41 minutes)
        arrival_seconds = self.L1_DISTANCE_KM / telemetry["sw_velocity_x_km_s"]
        arrival_minutes = round(arrival_seconds / 60, 1)

        # IMF Bz Prediction (Negative is dangerous for power grids)
        # High Kp strongly correlates with sustained southward (negative) Bz
        base_bz = -1.5 * kp 
        predicted_bz = round(base_bz + random.uniform(-5.0, 5.0), 2)

        return {
            "l1_telemetry": telemetry,
            "predictions": {
                "imf_bz_nt": predicted_bz,
                "bz_orientation": "Southward (Danger)" if predicted_bz < -2.0 else "Northward (Safe)",
                "cme_arrival_time_minutes": arrival_minutes,
                "early_warning_status": "ACTIVE" if arrival_minutes < 60 else "MONITORING"
            }
        }


# ==============================================================================
# SUBSYSTEM 1: NAVIC & IONOSPHERIC DISRUPTION ARCHITECTURE
# ==============================================================================
class NavICPredictor:
    """
    Builds an Ionospheric Scintillation Predictor for NavIC.
    Calculates TEC and provides positional error correction matrices.
    """
    # Indian Subcontinent Bounding Box
    LAT_RANGE = (8.0, 37.0)
    LON_RANGE = (68.0, 97.0)

    def calculate_tec(self, lat: float, kp: float) -> float:
        """Mock Total Electron Content (TEC) based on Kp and Equatorial Anomaly."""
        # India lies in the Equatorial Ionospheric Anomaly (EIA) region (approx 15-20 deg lat)
        anomaly_factor = 1.0 + math.exp(-((lat - 15.0)**2) / 20.0)
        base_tec = 20.0  # TEC Units (TECU)
        return round(base_tec * anomaly_factor * (1 + (kp * 0.5)), 2)

    def generate_correction_matrix(self, kp: float) -> List[Dict[str, Any]]:
        """Generates a matrix of signal delays and correction vectors for edge devices."""
        matrix = []
        # Create a sparse 3x3 grid over India for the matrix
        for lat in [10.0, 22.0, 34.0]:
            for lon in [70.0, 80.0, 90.0]:
                tec = self.calculate_tec(lat, kp)
                # GPS/NavIC L5 band frequency ~1176.45 MHz. Delay ~ 40.3 * TEC / f^2
                # Simplified multiplier for mock error in meters:
                error_meters = round((tec * 0.15) * (1 + random.uniform(0.01, 0.1)), 2)
                
                matrix.append({
                    "lat": lat,
                    "lon": lon,
                    "tec_units": tec,
                    "scintillation_s4_index": round(min(1.0, tec / 100.0), 3),
                    "navic_l5_error_meters": error_meters,
                    "correction_vector": {"dx": round(-error_meters * 0.4, 2), "dy": round(-error_meters * 0.6, 2)}
                })
        return matrix


# ==============================================================================
# SUBSYSTEM 2: LOCALIZED POWER GRID GIC SIMULATOR
# ==============================================================================
class GICSimulator:
    """
    Models regional geomagnetic variations (dB/dt) using Indian magnetometer data
    and calculates Geomagnetically Induced Currents (GIC) across mock grid nodes.
    """
    GRID_NODES = [
        {"id": "NR-DEL-01", "name": "Delhi 400kV", "lat": 28.6, "resistance_ohms": 0.5},
        {"id": "ER-KOL-04", "name": "Kolkata 400kV", "lat": 22.5, "resistance_ohms": 0.4},
        {"id": "WR-MUM-02", "name": "Mumbai 765kV", "lat": 19.0, "resistance_ohms": 0.3},
        {"id": "SR-BLR-03", "name": "Bangalore 400kV", "lat": 12.9, "resistance_ohms": 0.6},
    ]

    def simulate_grid(self, kp: float, imf_bz: float) -> Dict[str, Any]:
        """Calculates GIC and runs the Smart Grid Advisory AI."""
        node_results = []
        topology_changes = []

        # dB/dt scales non-linearly with Kp, and spikes if IMF Bz is strongly negative
        bz_factor = abs(imf_bz) if imf_bz < 0 else 1.0
        base_db_dt = (kp ** 1.5) * bz_factor

        for node in self.GRID_NODES:
            # Regional anomaly: higher latitudes in India (Delhi) see slightly higher dB/dt
            lat_factor = node["lat"] / 20.0
            db_dt = round(base_db_dt * lat_factor * random.uniform(0.8, 1.2), 2)
            
            # Induced Electric Field E (mV/km) -> Simplified to Amperes for GIC
            # I = V/R, where V is induced along the transmission lines
            gic_amps = round((db_dt * 2.5) / node["resistance_ohms"], 2)

            # Smart Advisory Logic
            status = "NORMAL"
            action = "None"
            if gic_amps > 100.0:
                status = "CRITICAL"
                action = "EMERGENCY: Disconnect transformer ground wires to prevent melting. Prepare for minor blackouts."
                topology_changes.append({"node_id": node["id"], "action": "DISCONNECT_GROUND_WIRE"})
            elif gic_amps > 40.0:
                status = "WARNING"
                action = "PREPARE: Reduce power load through transformers to prevent overheating."

            node_results.append({
                "node_id": node["id"],
                "node_name": node["name"],
                "regional_db_dt_nT_min": db_dt,
                "gic_amperes": gic_amps,
                "node_status": status,
                "recommended_action": action
            })

        return {
            "transformer_nodes": node_results,
            "automated_topology_advisory": topology_changes if topology_changes else "Grid is stable. No action needed."
        }


# ==============================================================================
# SUBSYSTEM 3: SATELLITE ORBITAL DRAG CALCULATOR
# ==============================================================================
class OrbitalDragSimulator:
    """
    Models thermospheric expansion from plasma/Kp trends.
    Calculates dynamic orbital decay for LEO satellites.
    """
    # E.g., ISRO's RISAT or EOS satellites in Low Earth Orbit
    LEO_SATELLITES = [
        {"id": "EOS-04", "altitude_km": 529.0, "mass_kg": 1700.0, "area_m2": 8.5},
        {"id": "RISAT-2B", "altitude_km": 556.0, "mass_kg": 615.0, "area_m2": 5.0}
    ]

    def calculate_decay(self, kp: float, plasma_density: float) -> List[Dict[str, Any]]:
        """Calculates altitude drop and issues proactive fuel-burn alerts."""
        results = []
        
        # Thermospheric density increases exponentially during storms
        # Base density at 500km ~ 1e-12 kg/m^3
        density_multiplier = 1.0 + (kp ** 2) / 10.0 + (plasma_density / 20.0)
        
        for sat in self.LEO_SATELLITES:
            # Simplified drag acceleration: a = 0.5 * Cd * (A/m) * rho * v^2
            # We map this directly to a daily altitude decay metric for the mock
            base_decay_meters_per_day = 15.0 * (sat["area_m2"] / sat["mass_kg"]) * 1000.0
            decay_meters = round(base_decay_meters_per_day * density_multiplier, 2)
            
            alert = "NOMINAL"
            fuel_burn = 0.0
            if decay_meters > 50.0:
                alert = "MANEUVER_REQUIRED"
                fuel_burn = round((decay_meters - 10.0) * 0.05, 2) # Mock kg of propellant

            results.append({
                "satellite_id": sat["id"],
                "current_altitude_km": sat["altitude_km"],
                "projected_decay_meters_per_day": decay_meters,
                "drag_multiplier": round(density_multiplier, 2),
                "alert_level": alert,
                "recommended_station_keeping_burn_kg": fuel_burn
            })
        return results


# ==============================================================================
# UNIFIED ORCHESTRATOR: ANTIGRAVITY SUITE
# ==============================================================================
class AntigravitySuite:
    def __init__(self):
        self.aditya = AdityaL1Predictor()
        self.navic = NavICPredictor()
        self.grid = GICSimulator()
        self.orbital = OrbitalDragSimulator()

    def run_full_diagnostics(self, kp: float, speed: float, density: float) -> Dict[str, Any]:
        """Runs all subsystems and aggregates the JSON payload."""
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # 1. Advanced Predictive Core
        core_preds = self.aditya.predict_cme_and_imf(kp, speed, density)
        imf_bz = core_preds["predictions"]["imf_bz_nt"]
        
        # 2. NavIC & Ionosphere
        navic_matrix = self.navic.generate_correction_matrix(kp)
        
        # 3. Power Grid GIC
        grid_sim = self.grid.simulate_grid(kp, imf_bz)
        
        # 4. Satellite Drag
        orbit_sim = self.orbital.calculate_decay(kp, density)

        # Output Unified Schema
        return {
            "schema_version": "2.0-advanced",
            "timestamp": timestamp,
            "global_inputs": {
                "planetary_kp_index": kp,
                "solar_wind_speed_km_s": speed,
                "solar_wind_density_p_cc": density
            },
            "subsystems": {
                "advanced_predictive_core": core_preds,
                "navic_ionospheric_disruption": {
                    "correction_matrix_resolution": "3x3_India_Grid",
                    "regional_telemetry": navic_matrix
                },
                "localized_power_grid_gic": grid_sim,
                "satellite_orbital_drag": orbit_sim
            }
        }

if __name__ == "__main__":
    # Test the architecture with severe geomagnetic storm inputs (Kp = 7.5)
    suite = AntigravitySuite()
    output_json = suite.run_full_diagnostics(kp=7.5, speed=750.0, density=25.0)
    print(json.dumps(output_json, indent=2))
