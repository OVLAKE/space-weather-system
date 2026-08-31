"""
Test suite for the Space Weather Decision Support API.

Covers:
- safe_float() edge cases
- Risk evaluation boundary values
- API endpoints with mocked NOAA data
- Cache fallback when NOAA is down
- Cold-start safe defaults
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app, safe_float, evaluate_kp_risk, evaluate_wind_risk, _cache


client = TestClient(app)


# ===================================================================
# Unit tests: safe_float()
# ===================================================================

class TestSafeFloat:
    def test_normal_float(self):
        assert safe_float(3.67) == 3.67

    def test_integer(self):
        assert safe_float(5) == 5.0

    def test_zero(self):
        assert safe_float(0) == 0.0

    def test_string_number(self):
        assert safe_float("4.2") == 4.2

    def test_none_returns_default(self):
        assert safe_float(None) is None

    def test_none_returns_custom_default(self):
        assert safe_float(None, default=0.0) == 0.0

    def test_empty_string(self):
        assert safe_float("") is None

    def test_na_string(self):
        assert safe_float("N/A") is None

    def test_null_string(self):
        assert safe_float("null") is None

    def test_nan(self):
        assert safe_float(float("nan")) is None

    def test_negative(self):
        assert safe_float(-2.5) == -2.5


# ===================================================================
# Unit tests: evaluate_kp_risk()
# ===================================================================

class TestEvaluateKpRisk:
    def test_normal_low(self):
        result = evaluate_kp_risk(0.0)
        assert result["level"] == "NORMAL"

    def test_normal_boundary(self):
        result = evaluate_kp_risk(3.99)
        assert result["level"] == "NORMAL"

    def test_unsettled_boundary(self):
        result = evaluate_kp_risk(4.0)
        assert result["level"] == "UNSETTLED"

    def test_unsettled_high(self):
        result = evaluate_kp_risk(4.99)
        assert result["level"] == "UNSETTLED"

    def test_warning_boundary(self):
        result = evaluate_kp_risk(5.0)
        assert result["level"] == "WARNING"

    def test_warning_high(self):
        result = evaluate_kp_risk(6.99)
        assert result["level"] == "WARNING"

    def test_critical_boundary(self):
        result = evaluate_kp_risk(7.0)
        assert result["level"] == "CRITICAL"

    def test_critical_extreme(self):
        result = evaluate_kp_risk(9.0)
        assert result["level"] == "CRITICAL"

    def test_all_have_action(self):
        for kp in [0, 4, 5, 7]:
            result = evaluate_kp_risk(kp)
            assert "action" in result
            assert len(result["action"]) > 0


# ===================================================================
# Unit tests: evaluate_wind_risk()
# ===================================================================

class TestEvaluateWindRisk:
    def test_normal(self):
        result = evaluate_wind_risk(300.0)
        assert result["level"] == "NORMAL"

    def test_normal_boundary(self):
        result = evaluate_wind_risk(499.9)
        assert result["level"] == "NORMAL"

    def test_warning_boundary(self):
        result = evaluate_wind_risk(500.0)
        assert result["level"] == "WARNING"

    def test_warning_high(self):
        result = evaluate_wind_risk(799.9)
        assert result["level"] == "WARNING"

    def test_critical_boundary(self):
        result = evaluate_wind_risk(800.0)
        assert result["level"] == "CRITICAL"

    def test_critical_extreme(self):
        result = evaluate_wind_risk(1200.0)
        assert result["level"] == "CRITICAL"


# ===================================================================
# Integration tests: API endpoints with mocked NOAA data
# ===================================================================

# Sample NOAA Kp data (dict format, as NOAA currently returns)
MOCK_KP_DATA = [
    {"time_tag": "2026-08-31T00:00:00", "Kp": 2.33, "a_running": 9, "station_count": 8},
    {"time_tag": "2026-08-31T03:00:00", "Kp": 1.67, "a_running": 6, "station_count": 8},
    {"time_tag": "2026-08-31T06:00:00", "Kp": 3.00, "a_running": 12, "station_count": 8},
    {"time_tag": "2026-08-31T09:00:00", "Kp": 5.33, "a_running": 40, "station_count": 8},
    {"time_tag": "2026-08-31T12:00:00", "Kp": 7.67, "a_running": 132, "station_count": 8},
]

# Sample NOAA solar wind data (list-header format)
MOCK_SOLAR_WIND_DATA = [
    ["time_tag", "speed", "density", "temperature", "bx", "by", "bz", "bt", "vx", "vy", "vz", "propagated_time_tag"],
    ["2026-08-31T14:00:00Z", 423.3, 3.48, 118543.0, -3.87, 1.42, -1.25, 4.34, -422.6, 0.9, -22.7, "2026-08-31T14:52:16Z"],
    ["2026-08-31T14:30:00Z", 510.1, 5.12, 200000.0, -2.0, 3.0, -4.0, 5.5, -508.0, 2.1, -30.0, "2026-08-31T15:22:16Z"],
    ["2026-08-31T15:00:00Z", 825.0, 8.91, 350000.0, -5.0, 4.0, -7.0, 9.5, -820.0, 5.0, -50.0, "2026-08-31T15:52:16Z"],
]


def _mock_kp_response():
    """Create a mock requests.Response for Kp data."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = MOCK_KP_DATA
    mock.raise_for_status.return_value = None
    return mock


def _mock_solar_wind_response():
    """Create a mock requests.Response for solar wind data."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = MOCK_SOLAR_WIND_DATA
    mock.raise_for_status.return_value = None
    return mock


class TestKpEndpoint:
    @patch("main.requests.get")
    def test_returns_200(self, mock_get):
        mock_get.return_value = _mock_kp_response()
        response = client.get("/api/kp-live")
        assert response.status_code == 200

    @patch("main.requests.get")
    def test_returns_latest_kp(self, mock_get):
        mock_get.return_value = _mock_kp_response()
        data = client.get("/api/kp-live").json()
        # Latest entry in mock is Kp=7.67
        assert data["current_kp"] == 7.67

    @patch("main.requests.get")
    def test_critical_risk_for_high_kp(self, mock_get):
        mock_get.return_value = _mock_kp_response()
        data = client.get("/api/kp-live").json()
        assert data["risk_assessment"]["level"] == "CRITICAL"

    @patch("main.requests.get")
    def test_has_recent_history(self, mock_get):
        mock_get.return_value = _mock_kp_response()
        data = client.get("/api/kp-live").json()
        assert len(data["recent_history"]) > 0
        assert "timestamp" in data["recent_history"][0]
        assert "kp" in data["recent_history"][0]

    @patch("main.requests.get")
    def test_data_status_is_live(self, mock_get):
        mock_get.return_value = _mock_kp_response()
        data = client.get("/api/kp-live").json()
        assert data["data_status"] == "live"

    @patch("main.requests.get")
    def test_has_fetched_at(self, mock_get):
        mock_get.return_value = _mock_kp_response()
        data = client.get("/api/kp-live").json()
        assert "fetched_at" in data


class TestSolarWindEndpoint:
    @patch("main.requests.get")
    def test_returns_200(self, mock_get):
        mock_get.return_value = _mock_solar_wind_response()
        response = client.get("/api/solar-wind-live")
        assert response.status_code == 200

    @patch("main.requests.get")
    def test_returns_latest_speed(self, mock_get):
        mock_get.return_value = _mock_solar_wind_response()
        data = client.get("/api/solar-wind-live").json()
        # Latest entry is speed=825.0
        assert data["current_speed"] == 825.0

    @patch("main.requests.get")
    def test_critical_risk_for_high_speed(self, mock_get):
        mock_get.return_value = _mock_solar_wind_response()
        data = client.get("/api/solar-wind-live").json()
        assert data["risk_assessment"]["level"] == "CRITICAL"

    @patch("main.requests.get")
    def test_returns_density(self, mock_get):
        mock_get.return_value = _mock_solar_wind_response()
        data = client.get("/api/solar-wind-live").json()
        assert data["current_density"] == 8.91

    @patch("main.requests.get")
    def test_data_status_is_live(self, mock_get):
        mock_get.return_value = _mock_solar_wind_response()
        data = client.get("/api/solar-wind-live").json()
        assert data["data_status"] == "live"


# ===================================================================
# Integration tests: Cache fallback and cold-start defaults
# ===================================================================

class TestCacheFallback:
    @patch("main.requests.get")
    def test_kp_falls_back_to_cache(self, mock_get):
        # First call succeeds — primes cache
        mock_get.return_value = _mock_kp_response()
        data1 = client.get("/api/kp-live").json()
        assert data1["data_status"] == "live"

        # Second call fails — should return cached data
        mock_get.side_effect = Exception("NOAA is down")
        data2 = client.get("/api/kp-live").json()
        assert data2["data_status"] == "stale"
        assert data2["current_kp"] == data1["current_kp"]
        assert "stale_reason" in data2

    @patch("main.requests.get")
    def test_solar_wind_falls_back_to_cache(self, mock_get):
        # First call succeeds
        mock_get.return_value = _mock_solar_wind_response()
        data1 = client.get("/api/solar-wind-live").json()
        assert data1["data_status"] == "live"

        # Second call fails
        mock_get.side_effect = Exception("NOAA is down")
        data2 = client.get("/api/solar-wind-live").json()
        assert data2["data_status"] == "stale"
        assert data2["current_speed"] == data1["current_speed"]

    @patch("main.requests.get")
    def test_kp_cold_start_returns_defaults(self, mock_get):
        # Clear cache to simulate cold start
        _cache.clear()
        mock_get.side_effect = Exception("NOAA is down")
        data = client.get("/api/kp-live").json()
        assert data["data_status"] == "unavailable"
        assert data["current_kp"] == 0.0
        assert "stale_reason" in data

    @patch("main.requests.get")
    def test_solar_wind_cold_start_returns_defaults(self, mock_get):
        _cache.clear()
        mock_get.side_effect = Exception("NOAA is down")
        data = client.get("/api/solar-wind-live").json()
        assert data["data_status"] == "unavailable"
        assert data["current_speed"] == 0.0
        assert data["current_density"] == 0.0

    @patch("main.requests.get")
    def test_never_returns_http_error(self, mock_get):
        """A warning system must ALWAYS return 200."""
        _cache.clear()
        mock_get.side_effect = Exception("Total failure")
        
        r1 = client.get("/api/kp-live")
        assert r1.status_code == 200

        r2 = client.get("/api/solar-wind-live")
        assert r2.status_code == 200

        r3 = client.get("/api/kp-forecast")
        assert r3.status_code == 200


class TestKpForecastEndpoint:
    @patch("main.requests.get")
    def test_returns_200(self, mock_get):
        mock_get.return_value = _mock_kp_response()
        response = client.get("/api/kp-forecast")
        assert response.status_code == 200

    @patch("main.requests.get")
    def test_returns_forecast(self, mock_get):
        mock_get.return_value = _mock_kp_response()
        data = client.get("/api/kp-forecast").json()
        assert "observation_time" in data
        assert "current_kp" in data
        assert "forecasts" in data
        assert len(data["forecasts"]) == 3
        assert "forecast_time" in data["forecasts"][0]
        assert "forecasted_kp" in data["forecasts"][0]
        assert "risk_assessment" in data["forecasts"][0]
        assert "model_info" in data

    @patch("main.requests.get")
    def test_forecast_fallback_to_cache(self, mock_get):
        _cache.clear()
        # First call succeeds — primes cache
        mock_get.return_value = _mock_kp_response()
        data1 = client.get("/api/kp-forecast").json()
        
        # Second call fails — should return cached data
        mock_get.side_effect = Exception("NOAA is down")
        data2 = client.get("/api/kp-forecast").json()
        assert data2["data_status"] == "stale"
        assert data2["forecasts"][0]["forecasted_kp"] == data1["forecasts"][0]["forecasted_kp"]

    @patch("main.requests.get")
    def test_forecast_cold_start_returns_defaults(self, mock_get):
        _cache.clear()
        mock_get.side_effect = Exception("NOAA is down")
        data = client.get("/api/kp-forecast").json()
        assert data["data_status"] == "unavailable"
        assert data["current_kp"] == 0.0
        assert len(data["forecasts"]) == 3
        assert data["forecasts"][0]["forecasted_kp"] == 0.0


class TestHealthEndpoint:
    def test_root_returns_online(self):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "online"
