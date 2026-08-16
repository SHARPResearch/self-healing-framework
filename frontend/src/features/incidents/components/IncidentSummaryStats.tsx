import type { DeltaStat } from "../types";

interface IncidentSummaryStatsProps {
  stats: DeltaStat[];
}

export function IncidentSummaryStats({ stats }: IncidentSummaryStatsProps) {
  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
      {stats.map((stat) => (
        <div key={stat.id} className="flex flex-col gap-2">
          <span className="text-sm text-muted-foreground">{stat.label}</span>
          <div className="flex items-center gap-2">
            <span className="font-mono text-4xl font-semibold tracking-tight">{stat.value}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
