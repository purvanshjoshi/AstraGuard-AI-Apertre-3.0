import { useState } from 'react';
import { SatelliteCard } from './SatelliteCard';
import { PhaseTimeline } from './PhaseTimeline';
import { OrbitMap } from './OrbitMap';
import { AnomalyFeed } from './AnomalyFeed';
import { useDashboard } from '../../context/DashboardContext';
import { AnomalyEvent } from '../../types/dashboard';

export const MissionPanel: React.FC<{ onSelectSatellite?: (satId: string) => void }> = ({ onSelectSatellite }) => {
  const { state, send } = useDashboard();
  const { satellites, phases, anomalies } = state.mission;

  const [selectedSatId, setSelectedSatId] = useState<string | null>(null);
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyEvent | null>(null);

  const selectedSat = satellites.find((s) => s.id === selectedSatId) || null;

  const handleAcknowledgeAnomaly = (id: string) => {
    send({
      type: 'anomaly_ack', // Using lowercase to match types/websocket definition
      payload: { id },
      timestamp: new Date().toISOString()
    });
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top: Satellite Tracker from #87 */}
      <section className="glow-teal/50">
        <h2 className="text-2xl font-bold mb-6 text-teal-400 glow-teal flex items-center">
          Satellite Status{' '}
          <span className="ml-2 text-sm bg-teal-500/20 px-3 py-1 rounded-full">
            {satellites.filter((s) => s.status === 'Nominal').length}/6 Nominal
          </span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          {satellites.map((sat) => (
            <SatelliteCard
              key={sat.id}
              {...sat}
              isSelected={selectedSatId === sat.id}
              onClick={() => {
                setSelectedSatId(sat.id);
                onSelectSatellite?.(sat.orbitSlot);
              }}
            />
          ))}
        </div>
      </section>

      {/* 3-Column Layout: Map (2x) + Feed (1x) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Map Section (2x width) */}
        <section className="lg:col-span-2 glow-teal rounded-2xl border border-teal-500/30 p-4 bg-black/50 backdrop-blur-xl">
          <h3 className="text-lg font-bold text-teal-400 mb-4 glow-teal">Orbit Visualization</h3>
          <OrbitMap
            satellites={satellites}
            selectedSat={selectedSat}
            onSatClick={(sat) => {
              setSelectedSatId(sat.id);
              onSelectSatellite?.(sat.orbitSlot);
            }}
            anomalies={anomalies.filter((a) => !a.acknowledged)}
          />
        </section>

        {/* Anomaly Feed (1x width) */}
        <section className="glow-magenta rounded-2xl border border-magenta-500/30 p-0">
          <AnomalyFeed
            anomalies={anomalies}
            onAcknowledge={handleAcknowledgeAnomaly}
            onSelect={setSelectedAnomaly}
            selectedSat={selectedSat?.orbitSlot || null}
          />
        </section>
      </div>

      {/* Selected Items Debug Panel */}
      {(selectedSat || selectedAnomaly) && (
        <div className="p-4 bg-black/70 backdrop-blur-xl rounded-xl border border-teal-500/50 glow-teal grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          {selectedSat && (
            <div>
              <h4 className="font-bold text-teal-400 mb-2">Selected Satellite</h4>
              <div className="space-y-1 font-mono text-gray-300">
                <div>LEO-{selectedSat.orbitSlot} · {selectedSat.status}</div>
                <div className="text-xs opacity-75">{selectedSat.task} · {Math.round(selectedSat.latency)}ms</div>
              </div>
            </div>
          )}
          {selectedAnomaly && (
            <div>
              <h4 className="font-bold text-magenta-400 mb-2">Selected Anomaly</h4>
              <div className="space-y-1 font-mono text-gray-300">
                <div>{selectedAnomaly.satellite}</div>
                <div className="text-xs opacity-75">{selectedAnomaly.metric} · {selectedAnomaly.value}</div>
              </div>
            </div>
          )}
        </div>
      )}

      <PhaseTimeline phases={phases} />
    </div>
  );
};
