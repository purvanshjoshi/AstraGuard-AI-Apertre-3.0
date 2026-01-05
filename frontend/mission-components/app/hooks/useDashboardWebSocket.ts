import { useState, useEffect, useCallback, useRef, useReducer } from 'react';
import { WSMessage, TelemetryState } from '../types/websocket';
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
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);
    const reconnectAttempts = useRef(0);
    const maxReconnects = 5;

    const connect = useCallback(() => {
        try {
            const ws = new WebSocket('ws://localhost:8080/dashboard');
            wsRef.current = ws;

            ws.onopen = () => {
                setConnected(true);
                dispatch({ type: 'CONNECTION_STATUS', payload: 'connected' });
                reconnectAttempts.current = 0;
                console.log('[WS] Connected');
            };

            ws.onmessage = (event) => {
                try {
                    const msg: WSMessage = JSON.parse(event.data);
                    // Handle different message types mapping to reducer actions
                    if (msg.type === 'telemetry_snapshot') {
                        dispatch({ type: 'TELEMETRY_SNAPSHOT', payload: msg.payload });
                    } else {
                        dispatch({ type: msg.type.toUpperCase(), payload: msg.payload });
                    }
                } catch (e) {
                    console.error('[WS] Parse error', e);
                }
            };

            ws.onclose = () => {
                setConnected(false);
                dispatch({ type: 'CONNECTION_STATUS', payload: 'disconnected' });
                console.log('[WS] Disconnected - reconnecting...');
                scheduleReconnect();
            };

            ws.onerror = (error) => {
                console.error('[WS] Error:', error);
                ws.close();
            };
        } catch (error) {
            console.error('[WS] Connection failed:', error);
            scheduleReconnect();
        }
    }, []);

    const scheduleReconnect = () => {
        if (reconnectAttempts.current < maxReconnects) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
            reconnectAttempts.current++;
            reconnectTimeoutRef.current = setTimeout(connect, delay);
        }
    };

    // Fallback polling (mock implementation for now)
    useEffect(() => {
        let pollInterval: NodeJS.Timeout | undefined;
        if (!isConnected) {
            //   pollInterval = setInterval(() => {
            //     console.log('Polling fallback...'); 
            //     // In real app: fetch('/api/telemetry-fallback')...
            //   }, 5000);
        }
        return () => {
            if (pollInterval) clearInterval(pollInterval);
        };
    }, [isConnected]);

    useEffect(() => {
        connect();
        return () => {
            if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
            wsRef.current?.close();
        };
    }, [connect]);

    const send = useCallback((message: WSMessage) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(message));
            // Optimistic UI updates could go here
            if (message.type === 'anomaly_ack') {
                dispatch({ type: 'ANOMALY_ACK', payload: message.payload });
            }
        }
    }, []);

    return {
        state,
        isConnected,
        send,
        dispatch // For manual actions like ACK
    };
};
