import React, { useEffect, useState, useRef, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { Satellite, AnomalyEvent } from '../../types/dashboard';
import { getSatellitePosition, SatellitePoint } from '../../utils/orbital';

// Dynamically import Globe to avoid SSR issues with WebGL
const Globe = dynamic(() => import('react-globe.gl'), { ssr: false });

interface Props {
  satellites: Satellite[];
  selectedSat?: Satellite | null;
  onSatClick: (sat: Satellite) => void;
  anomalies: AnomalyEvent[];
}

export const OrbitMap: React.FC<Props> = ({ satellites, selectedSat, onSatClick, anomalies }) => {
  const globeEl = useRef<any>(null);
  const [points, setPoints] = useState<SatellitePoint[]>([]);

  // Calculate satellite positions (animation loop)
  useEffect(() => {
    const updatePositions = () => {
      const newPoints = satellites.map(getSatellitePosition);
      setPoints(newPoints);
    };

    // Update every 50ms for smooth-ish animation
    const interval = setInterval(updatePositions, 50);
    return () => clearInterval(interval);
  }, [satellites]);

  // Initial focus on selected satellite
  useEffect(() => {
    if (selectedSat && globeEl.current) {
      const satPoint = getSatellitePosition(selectedSat);
      // globeEl.current.pointOfView({ lat: satPoint.lat, lng: satPoint.lng, altitude: satPoint.alt + 0.5 }, 1000);
    }
  }, [selectedSat]);

  // Auto-rotate
  useEffect(() => {
    if (globeEl.current) {
      globeEl.current.controls().autoRotate = true;
      globeEl.current.controls().autoRotateSpeed = 0.5;
    }
  }, []);

  const ringsData = useMemo(() => {
    return anomalies.map(anomaly => {
      // Find satellite for anomaly
      const sat = satellites.find(s => s.orbitSlot === anomaly.satellite.split('-')[1]); // Hacky match based on mock formatting
      if (!sat) return null;
      const pos = getSatellitePosition(sat);
      return {
        lat: pos.lat,
        lng: pos.lng,
        alt: pos.alt,
        maxR: 5,
        propagationSpeed: 5,
        repeatPeriod: 1000,
        color: () => '#ef4444'
      }
    }).filter(Boolean);
  }, [anomalies, satellites]);

  return (
    <div className="relative w-full h-full bg-slate-950 rounded-sm border border-slate-900 overflow-hidden flex items-center justify-center">
      <Globe
        ref={globeEl}
        width={800} // Ideally responsive
        height={400}
        globeImageUrl="//unpkg.com/three-globe/example/img/earth-night.jpg"
        backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
        pointsData={points}
        pointAltitude="alt"
        pointColor="color"
        pointRadius={0.5}
        pointLabel={(d: any) => `
            <div style="background: rgba(15, 23, 42, 0.9); padding: 8px; border: 1px solid #334155; border-radius: 4px; color: white;">
                <div style="font-weight: bold; color: ${d.color}">${d.name}</div>
                <div style="font-size: 11px;">Status: ${d.status}</div>
            </div>
        `}
        onPointClick={(point: any) => {
          const originalSat = satellites.find(s => s.id === point.id);
          if (originalSat) onSatClick(originalSat);
        }}
        ringsData={ringsData}
        ringColor="color"
        ringMaxRadius="maxR"
        ringPropagationSpeed="propagationSpeed"
        ringRepeatPeriod="repeatPeriod"
        atmosphereColor="#3b82f6" // Blue atmosphere
        atmosphereAltitude={0.15}
      />

      {/* Overlay UI */}
      <div className="absolute top-4 right-4 bg-slate-900/80 backdrop-blur border border-slate-700 p-2 rounded text-xs text-slate-300">
        <div>Total Satellites: {satellites.length}</div>
        <div>Active Anomalies: {anomalies.length}</div>
      </div>
    </div>
  );
};
