export interface Satellite {
  id: string;
  name: string;
  status: 'Nominal' | 'Degraded' | 'Critical';
  orbit: string;
  orbitSlot: string;
  latency: number;
  task: string;
  signal: number;
}

export interface MissionPhase {
  name: string;
  status: 'complete' | 'active' | 'pending';
  progress: number;
  eta?: string;
  isActive: boolean;
}

export interface AnomalyEvent {
  id: string;
  message?: string;
  severity: 'Critical' | 'Warning' | 'Info';
  timestamp: string;
  satellite: string;
  metric: string;
  value: string;
  acknowledged: boolean;
}

export interface MissionState {
  name: string;
  phase: string;
  status: 'Nominal' | 'Degraded' | 'Critical';
  updated: string;
  anomalyCount: number;
  satellites: Satellite[];
  phases: MissionPhase[];
  anomalies: AnomalyEvent[];
}
