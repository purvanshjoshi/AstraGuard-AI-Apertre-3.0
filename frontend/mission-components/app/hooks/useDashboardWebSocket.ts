import { useState, useEffect, useCallback, useRef, useReducer } from 'react';
import { TelemetryState } from '../types/websocket';
import dashboardData from '../mocks/dashboard.json';
import systemsData from '../mocks/systems.json';
import telemetryData from '../mocks/telemetry.json';

// Use same initial state structure as context
export const initialState: TelemetryState = {
    mission: {
        satellites: dashboardData.mission.satellites as any[],
        phases: dashboardData.mission.phases as any[],
        anomalies: dashboardData.mission.anomalies as any[]
    },
    systems: {
        kpis: systemsData.kpis as any[],
        breakers: systemsData.breakers as any[],
        charts: telemetryData.charts as any,
        health: telemetryData.health as any[]
    },
    connection: 'connecting'
};

export const telemetryReducer = (state: TelemetryState, action: any): TelemetryState => {
    switch (action.type) {
        case 'TELEMETRY_SNAPSHOT':
            return {
                ...state,
                mission: action.payload.mission || state.mission,
                systems: action.payload.systems || state.systems
            };
        case 'TELEMETRY':
            return { ...state, systems: { ...state.systems, ...action.payload } };
        case 'TELEMETRY_UPDATE':
            return {
                ...state,
                mission: action.payload.mission ? { ...state.mission, ...action.payload.mission } : state.mission,
                systems: action.payload.systems ? { ...state.systems, ...action.payload.systems } : state.systems
            };
        case 'ANOMALY':
            return {
                ...state,
                mission: {
                    ...state.mission,
                    anomalies: [...state.mission.anomalies, action.payload]
                }
            };
        case 'ANOMALY_ACK':
            return {
                ...state,
                mission: {
                    ...state.mission,
                    anomalies: state.mission.anomalies.filter(a => a.id !== action.payload.id)
                }
            };
        case 'SATELLITES':
            return { ...state, mission: { ...state.mission, satellites: action.payload } };
        case 'KPI_UPDATE':
            return {
                ...state,
                systems: {
                    ...state.systems,
                    kpis: state.systems.kpis.map(kpi =>
                        kpi.id === action.payload.id ? action.payload : kpi
                    )
                }
            };
        case 'HEALTH_UPDATE':
            return {
                ...state,
                systems: {
                    ...state.systems,
                    health: state.systems.health.map(h =>
                        h.id === action.payload.id ? action.payload : h
                    )
                }
            };
        case 'CONNECTION_STATUS':
            return { ...state, connection: action.payload };
        default:
            return state;
    }
};

export const useDashboardWebSocket = () => {
    const [state, dispatch] = useReducer(telemetryReducer, initialState);
    const [isConnected, setConnected] = useState(false);

    // Replay State
    const [isReplayMode, setReplayMode] = useState(false);
    const [replayData, setReplayData] = useState<any[]>([]);
    const [replayProgress, setReplayProgress] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);

    const reconnectAttempts = useRef(0);

    const toggleReplayMode = async () => {
        if (!isReplayMode) {
            // Enter Replay Mode: Fetch session
            try {
                const res = await fetch('http://localhost:8002/api/v1/replay/session?incident_type=VOLTAGE_SPIKE');
                const data = await res.json();
                setReplayData(data.frames);
                setReplayProgress(0);
                setIsPlaying(true);
            } catch (e) {
                console.error("Failed to load replay session", e);
            }
        }
        setReplayMode(!isReplayMode);
    };

    const togglePlay = () => setIsPlaying(!isPlaying);

    const pollBackend = useCallback(async () => {
        if (isReplayMode) return; // Stop polling in replay mode

        try {
            // Fetch Status, Telemetry, Anomalies...
            const [statusRes, telemetryRes, historyRes] = await Promise.all([
                fetch('http://localhost:8002/api/v1/status'),
                fetch('http://localhost:8002/api/v1/telemetry/latest'),
                fetch('http://localhost:8002/api/v1/history/anomalies?limit=10')
            ]);

            const statusData = await statusRes.json();
            const telemetryDataRaw = await telemetryRes.json();
            const historyData = await historyRes.json();

            setConnected(true);
            dispatch({ type: 'CONNECTION_STATUS', payload: 'connected' });

            // Update KPIs with live data
            if (telemetryDataRaw.data) {
                const t = telemetryDataRaw.data;
                updateKPIs(t, dispatch);
            }

        } catch (error) {
            console.warn('[Polling] Failed - using mockup');
            setConnected(true);
        }
    }, [isReplayMode]);

    // Handle Replay Frame Updates
    useEffect(() => {
        if (isReplayMode && replayData && replayData.length > 0) {
            // Map progress 0-100 to frame index
            const frameIndex = Math.floor((replayProgress / 100) * (replayData.length - 1));
            const frame = replayData[frameIndex];

            if (frame) {
                updateKPIs(frame, dispatch);
            }
        }
    }, [isReplayMode, replayProgress, replayData]);

    // Effect for polling (only when not replay)
    useEffect(() => {
        if (isReplayMode) return;
        const interval = setInterval(pollBackend, 2000);
        pollBackend();
        return () => clearInterval(interval);
    }, [pollBackend, isReplayMode]);


    return {
        state,
        isConnected,
        send: () => { },
        dispatch,
        isReplayMode,
        toggleReplayMode,
        replayProgress,
        setReplayProgress,
        isPlaying,
        togglePlay
    };
};

// Helper
const updateKPIs = (t: any, dispatch: any) => {
    const kpiUpdates = [
        { id: 'voltage', label: 'Bus Voltage', value: `${t.voltage.toFixed(2)}V`, status: 'nominal', trend: 'stable' },
        { id: 'current', label: 'Total Current', value: `${t.current?.toFixed(2) || '0.00'}A`, status: 'nominal', trend: 'stable' },
        { id: 'temp', label: 'Core Temp', value: `${t.temperature.toFixed(1)}°C`, status: t.temperature > 50 ? 'warning' : 'nominal', trend: 'increasing' },
        { id: 'gyro', label: 'Gyro Stability', value: `${t.gyro.toFixed(4)}`, status: 'nominal', trend: 'stable' }
    ];
    kpiUpdates.forEach(kpi => dispatch({ type: 'KPI_UPDATE', payload: kpi }));
};
