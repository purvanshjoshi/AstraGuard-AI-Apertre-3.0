'use client';

import { useState, useEffect } from 'react';
import { MissionState } from '../../types/dashboard';
import { useDashboard } from '../../context/DashboardContext';

interface Props {
  data: MissionState;
}

const statusIcon = (status: MissionState['status']) => {
  const icons = { Nominal: '🟢', Degraded: '🟡', Critical: '🔴' };
  return icons[status];
};

export const DashboardHeader: React.FC<Props> = ({ data }) => {
  const { isConnected } = useDashboard();
  const [time, setTime] = useState(new Date().toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  }));

  useEffect(() => {
    const iv = setInterval(
      () =>
        setTime(
          new Date().toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
          })
        ),
      1000 * 30
    );
    return () => clearInterval(iv);
  }, []);

  return (
    <header className="h-[60px] bg-black/90 border-b border-teal-500/20 flex items-center px-6 fixed w-full z-50">
      <div className="flex items-center justify-between w-full">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-gradient-to-r from-teal-500 to-cyan-500 rounded-lg"></div>
          <h1 className="text-lg font-bold font-mono text-white tracking-tight">{data.name}</h1>
        </div>
        <div className="flex items-center space-x-4 text-xs text-gray-400">
          <span className={`px-2 py-0.5 rounded-full font-mono transition-all ${isConnected
              ? 'bg-green-500/10 text-green-400 border border-green-500/20 glow-green'
              : 'bg-red-500/10 text-red-500 border border-red-500/20 glow-red animate-pulse'
            }`}>
            {isConnected ? 'LIVE' : 'OFFLINE'}
          </span>
          <span className="text-teal-400">{data.phase}</span>
          <span>{statusIcon(data.status)}</span>
          <span>{time}</span>
        </div>
      </div>
    </header>
  );
};
