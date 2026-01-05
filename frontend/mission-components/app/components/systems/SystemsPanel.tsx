import React from 'react';
import systemsData from '../../mocks/systems.json';
import { KPICard } from './KPICard';
import { BreakerMatrix } from './BreakerMatrix';
import { MetricsCharts } from './MetricsCharts';
import { HealthTable } from './HealthTable';
import { useDashboard } from '../../context/DashboardContext';

export const SystemsPanel: React.FC = () => {
    const { state } = useDashboard();
    const { kpis, breakers, charts, health } = state.systems;

    // Render logic remains similar, but data comes from context
    return (
        <div className="space-y-12 max-w-7xl mx-auto">
            {/* KPI Row */}
            <section className="glow-magenta/50">
                <h2 className="text-2xl font-bold mb-8 text-magenta-400 glow-magenta">System Health Overview</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
                    {kpis.map(kpi => <KPICard key={kpi.id} {...kpi} />)}
                </div>
            </section>

            {/* Charts Grid */}
            <section className="glow-teal/50">
                <h2 className="text-2xl font-bold mb-8 text-teal-400 glow-teal">Telemetry Trends (Last 1h)</h2>
                <MetricsCharts data={charts} />
            </section>

            {/* Health Table */}
            <section>
                <h2 className="text-2xl font-bold mb-8 text-teal-400 glow-teal flex items-center">
                    Component Health <span className="ml-3 text-sm bg-teal-500/0 px-3 py-1 rounded-full font-mono text-teal-300 border border-teal-500/30">
                        {health.filter(h => h.status !== 'healthy').length} degraded
                    </span>
                </h2>
                <HealthTable data={health} />
            </section>

            {/* Breaker Matrix */}
            <BreakerMatrix breakers={breakers} services={systemsData.services} />
        </div>
    );
};
