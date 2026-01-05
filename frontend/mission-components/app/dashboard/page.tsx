'use client';

import { useState } from 'react';
import { MissionState } from '../types/dashboard';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { MissionPanel } from '../components/mission/MissionPanel';
import dashboardData from '../mocks/dashboard.json';

import { SystemsPanel } from '../components/systems/SystemsPanel';

import { DashboardProvider } from '../context/DashboardContext';

const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'mission' | 'systems'>('mission');
  const mission = dashboardData.mission as MissionState;

  return (
    <DashboardProvider>
      <div className="dashboard-container min-h-screen text-white font-mono antialiased">
        <DashboardHeader data={mission} />

        <div className="flex h-[calc(100vh-60px)] mt-[60px] flex-col">
          <nav
            className="sticky top-0 z-20 bg-black/80 backdrop-blur-md border-b border-teal-500/30 py-4 px-6 flex items-center justify-between flex-shrink-0"
            role="tablist"
            aria-label="Mission Control Tabs"
          >
            <div className="flex gap-2">
              <button
                role="tab"
                aria-selected={activeTab === 'mission'}
                aria-controls="mission-panel"
                id="mission-tab"
                className={`px-6 py-3 rounded-t-lg font-mono text-lg font-semibold transition-all duration-300 ${activeTab === 'mission'
                  ? 'bg-teal-500/10 border-b-2 border-teal-400 text-teal-300 glow-teal'
                  : 'text-gray-400 hover:text-teal-300 hover:bg-teal-500/5'
                  }`}
                onClick={() => setActiveTab('mission')}
              >
                Mission
              </button>

              <button
                role="tab"
                aria-selected={activeTab === 'systems'}
                aria-controls="systems-panel"
                id="systems-tab"
                className={`ml-2 px-6 py-3 rounded-t-lg font-mono text-lg font-semibold transition-all duration-300 ${activeTab === 'systems'
                  ? 'bg-cyan-500/10 border-b-2 border-cyan-400 text-cyan-300 glow-cyan'
                  : 'text-gray-400 hover:text-cyan-300 hover:bg-cyan-500/5'
                  }`}
                onClick={() => setActiveTab('systems')}
              >
                Systems
              </button>
            </div>
          </nav>

          <main className="flex-1 overflow-auto p-6 pt-4">
            <section
              id="mission-panel"
              role="tabpanel"
              aria-labelledby="mission-tab"
              aria-hidden={activeTab !== 'mission'}
              className={`transition-all duration-500 ${activeTab === 'mission' ? 'block' : 'hidden'}`}
            >
              <MissionPanel />
            </section>

            <section
              id="systems-panel"
              role="tabpanel"
              aria-labelledby="systems-tab"
              aria-hidden={activeTab !== 'systems'}
              className={`transition-all duration-500 ${activeTab === 'systems' ? 'block' : 'hidden'}`}
            >
              <SystemsPanel />
            </section>
          </main>
        </div>
      </div>
    </DashboardProvider>
  );
};

export default Dashboard;

