const BASE_URL = 'http://127.0.0.1:8000';

// This is the missing piece causing the red line in App.tsx!
export interface SpaceWeatherData {
    timestamp: string;
    risk_assessment: {
        level: string;
        action: string;
    };
    current_kp?: number;
    current_speed?: number;
    current_density?: number;
    kp_history?: Array<{ time: string; kp: number }>;
    wind_history?: Array<{ time: string; speed: number; density: number }>;
    [key: string]: any;
}

export const fetchKpData = async (): Promise<SpaceWeatherData | null> => {
    try {
        const response = await fetch(`${BASE_URL}/api/kp-live`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Could not fetch Kp-index data:", error);
        return null;
    }
};

export const fetchSolarWindData = async (): Promise<SpaceWeatherData | null> => {
    try {
        const response = await fetch(`${BASE_URL}/api/solar-wind-live`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Could not fetch Solar Wind data:", error);
        return null;
    }
};