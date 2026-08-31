import { useState, useEffect } from 'react';
import './App.css';

interface RiskAssessment {
  level: string;
  action: string;
}

interface KpHistoryItem {
  timestamp: string;
  kp: number;
}

interface KpData {
  timestamp: string;
  current_kp: number;
  risk_assessment: RiskAssessment;
  recent_history: KpHistoryItem[];
  data_status?: 'live' | 'stale' | 'unavailable';
  stale_reason?: string;
}

interface SolarWindHistoryItem {
  timestamp: string;
  speed: number;
  density: number;
}

interface SolarWindData {
  timestamp: string;
  current_speed: number;
  current_density: number;
  risk_assessment: RiskAssessment;
  recent_history: SolarWindHistoryItem[];
  data_status?: 'live' | 'stale' | 'unavailable';
  stale_reason?: string;
}

interface ForecastItem {
  forecast_time: string;
  forecasted_kp: number;
  risk_assessment: RiskAssessment;
}

interface ForecastData {
  observation_time: string;
  current_kp: number;
  forecasts: ForecastItem[];
  model_info: {
    model_name?: string;
    training_samples?: number;
    test_rmse?: number;
    test_r2?: number;
    warning?: string;
    error?: string;
  };
  data_status?: 'live' | 'stale' | 'unavailable';
  stale_reason?: string;
}

function App() {
  const [kp, setKp] = useState<KpData | null>(null);
  const [wind, setWind] = useState<SolarWindData | null>(null);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  const fetchData = async () => {
    setLoading(true);
    try {
      const [kpRes, windRes, forecastRes] = await Promise.all([
        fetch('/api/kp-live'),
        fetch('/api/solar-wind-live'),
        fetch('/api/kp-forecast')
      ]);

      if (!kpRes.ok || !windRes.ok || !forecastRes.ok) {
        throw new Error('API server returned error response.');
      }

      const kpJson = await kpRes.json();
      const windJson = await windRes.json();
      const forecastJson = await forecastRes.json();

      setKp(kpJson);
      setWind(windJson);
      setForecast(forecastJson);
      setError(null);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError('Could not connect to the backend decision support API. Ensure backend is running.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const getOverallDataStatus = () => {
    const statuses = [kp?.data_status, wind?.data_status, forecast?.data_status];
    if (statuses.includes('unavailable')) return 'unavailable';
    if (statuses.includes('stale')) return 'stale';
    return 'live';
  };

  const getThreatBadgeClass = (level: string = '') => {
    switch (level.toUpperCase()) {
      case 'CRITICAL':
        return 'threat-badge level-critical';
      case 'WARNING':
        return 'threat-badge level-warning';
      case 'UNSETTLED':
        return 'threat-badge level-unsettled';
      default:
        return 'threat-badge level-normal';
    }
  };

  const renderKpChart = (history: KpHistoryItem[]) => {
    if (!history || history.length === 0) return <div className="text-center font-mono">No data</div>;
    const width = 300;
    const height = 80;
    const padding = 10;
    
    const points = history.map((item, i) => {
      const x = padding + (i * (width - 2 * padding)) / (history.length - 1);
      const y = height - padding - (item.kp * (height - 2 * padding)) / 9;
      return { x, y, kp: item.kp, time: new Date(item.timestamp).toLocaleTimeString() };
    });

    const polylinePoints = points.map(p => `${p.x},${p.y}`).join(' ');

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg">
        {/* Horizontal grids */}
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="var(--border)" strokeWidth="0.5" />
        <line x1={padding} y1={height - padding - (4 * (height - 2 * padding)) / 9} x2={width - padding} y2={height - padding - (4 * (height - 2 * padding)) / 9} stroke="rgba(245, 158, 11, 0.3)" strokeDasharray="3" />
        <line x1={padding} y1={height - padding - (7 * (height - 2 * padding)) / 9} x2={width - padding} y2={height - padding - (7 * (height - 2 * padding)) / 9} stroke="rgba(239, 68, 68, 0.3)" strokeDasharray="3" />
        
        {/* Polyline */}
        <polyline points={polylinePoints} className="chart-line" />
        
        {/* Dots */}
        {points.map((p, idx) => (
          <circle
            key={idx}
            cx={p.x}
            cy={p.y}
            r="3"
            className="chart-dot"
          >
            <title>Time: {p.time}&#010;Kp: {p.kp}</title>
          </circle>
        ))}
      </svg>
    );
  };

  const renderSpeedChart = (history: SolarWindHistoryItem[]) => {
    if (!history || history.length === 0) return <div className="text-center font-mono">No data</div>;
    const width = 300;
    const height = 80;
    const padding = 10;
    
    // Find min and max for scaling
    const speeds = history.map(h => h.speed);
    const minSpeed = Math.min(...speeds, 300);
    const maxSpeed = Math.max(...speeds, 800);
    const speedRange = maxSpeed - minSpeed || 1;

    const points = history.map((item, i) => {
      const x = padding + (i * (width - 2 * padding)) / (history.length - 1);
      const y = height - padding - ((item.speed - minSpeed) * (height - 2 * padding)) / speedRange;
      return { x, y, speed: item.speed, time: new Date(item.timestamp).toLocaleTimeString() };
    });

    const polylinePoints = points.map(p => `${p.x},${p.y}`).join(' ');

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg">
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="var(--border)" strokeWidth="0.5" />
        <polyline points={polylinePoints} className="chart-line" style={{ stroke: '#3b82f6' }} />
        {points.map((p, idx) => (
          <circle
            key={idx}
            cx={p.x}
            cy={p.y}
            r="3"
            className="chart-dot"
            style={{ fill: '#3b82f6' }}
          >
            <title>Time: {p.time}&#010;Speed: {p.speed} km/s</title>
          </circle>
        ))}
      </svg>
    );
  };

  const overallStatus = getOverallDataStatus();

  return (
    <div className="dashboard-container">
      {/* Top Header Section */}
      <header className="dashboard-header">
        <div className="header-title-area">
          <h1>Space Weather Decision Support</h1>
          <p className="header-subtitle">Real-time geomagnetic activity & predictive alerts</p>
        </div>
        <div className="header-controls">
          <span className={`status-badge ${overallStatus}`}>
            <span className="status-pulse"></span>
            {overallStatus === 'live' ? 'NOAA Live' : overallStatus === 'stale' ? 'Stale (Fallback)' : 'Outage'}
          </span>
          <button 
            type="button" 
            className="refresh-btn" 
            onClick={fetchData} 
            disabled={loading}
          >
            {loading ? <span className="spinner"></span> : '🔄 Refresh'}
          </button>
        </div>
      </header>

      {/* Warning Banner if data is Stale/Unavailable */}
      {(overallStatus === 'stale' || error) && (
        <div className="warning-banner">
          <span className="warning-icon">⚠️</span>
          <span>
            {error || kp?.stale_reason || wind?.stale_reason || 'Currently displaying stale NOAA telemetry cache due to connection issues.'}
          </span>
        </div>
      )}

      {/* Metric Cards Grid */}
      <main className="dashboard-grid">
        {/* Card 1: Planetary Kp Index */}
        <section className="metric-card">
          <div className="card-header">
            <h2>Kp Planetary Index</h2>
            <span className="card-icon">🌍</span>
          </div>
          <div className="metric-display">
            <span className="metric-value">{kp ? kp.current_kp.toFixed(2) : '--'}</span>
            <span className="metric-label">Geomagnetic Activity</span>
          </div>
          <div className="metric-details">
            <div className="detail-row">
              <span className="detail-label">Status Level:</span>
              <span className={getThreatBadgeClass(kp?.risk_assessment.level)}>
                {kp ? kp.risk_assessment.level : 'Unknown'}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Observation UTC:</span>
              <span className="detail-value">
                {kp ? new Date(kp.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--'}
              </span>
            </div>
          </div>
          <div className="chart-box">
            <span className="chart-title">Last 10 Measurements (Kp)</span>
            <div className="chart-wrapper">
              {kp ? renderKpChart(kp.recent_history) : <span className="spinner"></span>}
            </div>
          </div>
        </section>

        {/* Card 2: Solar Wind Plasma */}
        <section className="metric-card">
          <div className="card-header">
            <h2>Solar Wind Plasma</h2>
            <span className="card-icon">☀️</span>
          </div>
          <div className="metric-display">
            <span className="metric-value" style={{ fontSize: '28px' }}>
              {wind ? `${Math.round(wind.current_speed)} km/s` : '--'}
            </span>
            <span className="metric-label">Solar Wind Speed</span>
          </div>
          <div className="metric-details">
            <div className="detail-row">
              <span className="detail-label">Wind Density:</span>
              <span className="detail-value">
                {wind ? `${wind.current_density.toFixed(2)} p/cc` : '--'}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Wind Threat:</span>
              <span className={getThreatBadgeClass(wind?.risk_assessment.level)}>
                {wind ? wind.risk_assessment.level : 'Unknown'}
              </span>
            </div>
          </div>
          <div className="chart-box">
            <span className="chart-title">Last 10 Speed Values (km/s)</span>
            <div className="chart-wrapper">
              {wind ? renderSpeedChart(wind.recent_history) : <span className="spinner"></span>}
            </div>
          </div>
        </section>

        {/* Card 3: ML Forecast Card */}
        <section className="metric-card" style={{ borderLeft: '4px solid var(--accent)' }}>
          <div className="card-header">
            <h2>Predictive Forecast</h2>
            <span className="card-icon">🧠</span>
          </div>
          <div className="metric-display">
            <span className="metric-value" style={{ color: 'var(--accent)' }}>
              {forecast && forecast.forecasts.length > 0 ? forecast.forecasts[0].forecasted_kp.toFixed(2) : '--'}
            </span>
            <span className="metric-label">Next Kp Prediction (+3h)</span>
          </div>
          <div className="metric-details" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ fontWeight: 600, fontSize: '13px', borderBottom: '1px solid var(--border)', paddingBottom: '4px', marginBottom: '4px' }}>
              Forecast Timeline
            </div>
            {forecast && forecast.forecasts.map((f, idx) => (
              <div className="detail-row" key={idx} style={{ fontSize: '12px', alignItems: 'center' }}>
                <span className="detail-value" style={{ fontFamily: 'var(--mono)' }}>
                  {new Date(f.forecast_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                <span style={{ fontWeight: 700, color: 'var(--text-h)' }}>
                  Kp {f.forecasted_kp.toFixed(2)}
                </span>
                <span className={getThreatBadgeClass(f.risk_assessment.level)} style={{ padding: '2px 6px', fontSize: '10px' }}>
                  {f.risk_assessment.level}
                </span>
              </div>
            ))}
            {!forecast && <div className="text-center">--</div>}
          </div>
          <div className="chart-box">
            <span className="chart-title">ML Model Quality</span>
            <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {forecast && forecast.model_info && !forecast.model_info.error ? (
                <>
                  <div className="detail-row">
                    <span className="detail-label">Algorithm:</span>
                    <span className="detail-value">{forecast.model_info.model_name || 'Random Forest'}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Test Set R²:</span>
                    <span className="detail-value">
                      {forecast.model_info.test_r2 !== undefined ? forecast.model_info.test_r2.toFixed(3) : 'N/A'}
                    </span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Test Set RMSE:</span>
                    <span className="detail-value">
                      {forecast.model_info.test_rmse !== undefined ? forecast.model_info.test_rmse.toFixed(3) : 'N/A'}
                    </span>
                  </div>
                </>
              ) : (
                <div style={{ color: 'var(--text)', fontStyle: 'italic' }}>
                  {forecast?.model_info?.error || 'Forecast model state unavailable.'}
                </div>
              )}
            </div>
          </div>
        </section>
      </main>

      {/* Mitigation Action Panel & Educational explainer */}
      <section className="panels-section">
        {/* Mitigation Instructions */}
        <article className="info-panel">
          <h3>Mitigation Action Guidelines</h3>
          <div className="action-guidelines">
            <div className="action-item">
              <span className="action-item-icon">📡</span>
              <div>
                <strong>HF Communications & Navigation</strong>
                <p style={{ margin: '4px 0 0', color: 'var(--text)', fontSize: '13px' }}>
                  {kp?.risk_assessment.level === 'CRITICAL' 
                    ? 'CRITICAL: Severe disruption likely. Switch to satellite links; restrict polar HF frequencies.' 
                    : kp?.risk_assessment.level === 'WARNING' 
                    ? 'WARNING: Minor degradation possible. Monitor signal strength on HF bands.' 
                    : 'NOMINAL: Normal HF propagation and GPS services.'}
                </p>
              </div>
            </div>

            <div className="action-item">
              <span className="action-item-icon">✈️</span>
              <div>
                <strong>Aviation Operations</strong>
                <p style={{ margin: '4px 0 0', color: 'var(--text)', fontSize: '13px' }}>
                  {kp?.risk_assessment.level === 'CRITICAL' 
                    ? 'CRITICAL: Reroute polar passenger routes south of affected geomagnetic latitudes.' 
                    : 'NOMINAL: Normal operations on all air lanes.'}
                </p>
              </div>
            </div>

            <div className="action-item">
              <span className="action-item-icon">⚡</span>
              <div>
                <strong>Power Grid Operators</strong>
                <p style={{ margin: '4px 0 0', color: 'var(--text)', fontSize: '13px' }}>
                  {kp?.risk_assessment.level === 'CRITICAL' 
                    ? 'CRITICAL: High GIC risk. Configure grid lines for line resistance; monitor transformer voltages.' 
                    : 'NOMINAL: Ground currents within safe nominal tolerances.'}
                </p>
              </div>
            </div>
          </div>
        </article>

        {/* Educational Content */}
        <article className="info-panel">
          <h3>Understanding Space Weather</h3>
          <div className="educational-list">
            <div className="edu-item">
              <h4>What is the Planetary Kp-Index?</h4>
              <p>
                The Kp-index is a scale from 0 to 9 used to measure geomagnetic activity. It summarizes disturbances in the Earth's magnetic field. Values &ge; 5 represent geomagnetic storm alerts.
              </p>
            </div>
            <div className="edu-item">
              <h4>Why measure Solar Wind Speed & Density?</h4>
              <p>
                Solar wind is a constant stream of plasma from the sun. Fast solar wind (&gt; 500 km/s) or high densities trigger geomagnetic storms when colliding with the Earth's magnetosphere.
              </p>
            </div>
            <div className="edu-item">
              <h4>How does ML Forecasting work?</h4>
              <p>
                A Random Forest regressor analyses Kp history (lag observations) and trends. It learns historical patterns to forecast the Kp value for the next 3 hours, offering early-warning warning alerts.
              </p>
            </div>
          </div>
        </article>
      </section>

      {/* Footer Info */}
      <footer style={{ borderTop: '1px solid var(--border)', paddingTop: '16px', color: 'var(--text)', fontSize: '12px', textAlign: 'center', marginTop: '24px' }}>
        Space Weather Decision Support System • Local Time: {lastRefreshed.toLocaleTimeString()} • Data refreshed every 30 seconds
      </footer>
    </div>
  );
}

export default App;
