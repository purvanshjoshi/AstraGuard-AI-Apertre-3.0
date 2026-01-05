'use client';

import { Satellite } from '../../types/dashboard';

interface Props extends Satellite {
  onClick?: () => void;
  isSelected?: boolean;
}

export const SatelliteCard: React.FC<Props> = ({
  orbitSlot,
  status,
  latency,
  task,
  signal,
  onClick,
  isSelected,
}) => {
  const statusConfig = {
    Nominal: {
      icon: '🟢',
      borderClass: 'border-cyan-500/30 hover:border-cyan-400',
      glowClass: 'glow-cyan',
      ringClass: 'ring-cyan-500/50',
      barClass: 'from-cyan-400 to-cyan-600',
    },
    Degraded: {
      icon: '🟡',
      borderClass: 'border-amber-500/30 hover:border-amber-400',
      glowClass: 'glow-amber',
      ringClass: 'ring-amber-500/50',
      barClass: 'from-amber-400 to-amber-600',
    },
    Critical: {
      icon: '🔴',
      borderClass: 'border-red-500/30 hover:border-red-400',
      glowClass: 'glow-red',
      ringClass: 'ring-red-500/50',
      barClass: 'from-red-400 to-red-600',
    },
  }[status];

  return (
    <div
      className={`group p-4 rounded-xl border-2 bg-black/30 backdrop-blur-sm cursor-pointer transition-all duration-300 hover:scale-105 hover:-translate-y-1 hover:shadow-2xl ${statusConfig.glowClass
        } ${statusConfig.borderClass} ${isSelected ? `ring-4 ${statusConfig.ringClass} scale-105` : ''
        }`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-mono opacity-75">LEO-{orbitSlot}</span>
        <span className="text-xl">{statusConfig.icon}</span>
      </div>
      <div className="text-lg font-bold font-mono text-white mb-1 truncate">{status}</div>
      <div className="text-xs space-y-1 opacity-75 mb-3">
        <div>{Math.round(latency)}ms | {task}</div>
        <div>Signal: {signal}%</div>
      </div>
      <div className="w-full bg-black/50 rounded-full h-2">
        <div
          className={`bg-gradient-to-r ${statusConfig.barClass} h-2 rounded-full transition-all`}
          style={{ width: `${Math.min(signal, 100)}%` }}
        />
      </div>
    </div>
  );
};
