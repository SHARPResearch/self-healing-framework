import { useState } from "react";
import { IncidentTrendChart } from "./IncidentTrendChart";
import { IncidentSummaryStats } from "./IncidentSummaryStats";
import { ReliabilityMetricsList } from "./ReliabilityMetricsList";
import { incidentSummaryStats, incidentTrendByRange, reliabilityMetrics } from "../data/mockData";
import type { IncidentReportRange } from "../types";

const rangeOptions: { value: IncidentReportRange; label: string }[] = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
];

export function IncidentReportCard() {
  const [range, setRange] = useState<IncidentReportRange>("7d");

  return (
    <div className="rounded-xl border border-border/60 p-4">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h3 className="text-base font-semibold">Incident report</h3>
        <select
          value={range}
          onChange={(e) => setRange(e.target.value as IncidentReportRange)}
          aria-label="Incident report time range"
          className="cursor-pointer rounded-md border border-input bg-background px-3 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {rangeOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Incidents opened per day across all services.
      </p>

      <IncidentTrendChart data={incidentTrendByRange[range]} />

      <div className="mt-6 border-t border-border/60 pt-6">
        <IncidentSummaryStats stats={incidentSummaryStats} />
      </div>

      <div className="mt-2">
        <ReliabilityMetricsList metrics={reliabilityMetrics} />
      </div>
    </div>
  );
}
