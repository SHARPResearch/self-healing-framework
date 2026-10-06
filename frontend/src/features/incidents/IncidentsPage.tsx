import { useSearchParams } from "react-router-dom";
import { X } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Button } from "@/components/ui/button";
import { SimulateAnomalyTrigger } from "@/shared/components/SimulateAnomalyTrigger";
import { RlPolicyEvaluationBanner } from "@/shared/components/RlPolicyEvaluationBanner";
import { useRemediationStore } from "@/shared/store/remediationStore";
import { IncidentReportCard } from "./components/IncidentReportCard";
import { IncidentFeed } from "@/features/dashboard/components/IncidentFeed";
import { recentIncidents } from "@/features/dashboard/data/mockData";

export function IncidentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = searchParams.get("filter");
  const liveIncidents = useRemediationStore((s) => s.liveIncidents);

  const allIncidents = [...liveIncidents, ...recentIncidents];
  const incidents = filter
    ? allIncidents.filter((i) => i.serviceId === filter)
    : allIncidents;

  return (
    <AppShell pageTitle="Incidents">
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            Simulate an anomaly to see the adaptive decision engine evaluate and execute a
            remediation live.
          </p>
          <SimulateAnomalyTrigger />
        </div>
        <RlPolicyEvaluationBanner />

        {filter && (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-muted/40 px-4 py-2.5 text-sm">
            <span>
              Filtered to <span className="font-mono font-medium">{filter}</span>
              <span className="ml-2 text-muted-foreground">
                {incidents.length} {incidents.length === 1 ? "incident" : "incidents"}
              </span>
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSearchParams({})}
              className="h-auto px-2 py-1"
            >
              <X className="mr-1 size-3.5" />
              Clear
            </Button>
          </div>
        )}

        <IncidentReportCard />

        <div className="rounded-xl border border-border/60 p-4">
          <IncidentFeed incidents={incidents} />
        </div>
      </div>
    </AppShell>
  );
}
