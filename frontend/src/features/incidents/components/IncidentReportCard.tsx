import { IncidentTrendChart } from "./IncidentTrendChart";
import { IncidentSummaryStats } from "./IncidentSummaryStats";
import { ReliabilityMetricsList } from "./ReliabilityMetricsList";
import { incidentSummaryStats, incidentTrendByRange, reliabilityMetrics } from "../data/mockData";

export function IncidentReportCard() {
  return (
    <div className="rounded-xl border border-border/60 p-4">
      <h3 className="mb-1 text-base font-semibold">Incident report</h3>
      <p className="mb-4 text-sm text-muted-foreground">
        Incidents opened per day across all services.
      </p>

      <IncidentTrendChart data={incidentTrendByRange["7d"]} />

      <div className="mt-6 border-t border-border/60 pt-6">
        <IncidentSummaryStats stats={incidentSummaryStats} />
      </div>

      <div className="mt-2">
        <ReliabilityMetricsList metrics={reliabilityMetrics} />
      </div>
    </div>
  );
}
