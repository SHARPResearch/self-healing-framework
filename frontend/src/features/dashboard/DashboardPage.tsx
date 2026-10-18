import { AppShell } from "@/shared/layout/AppShell";
import { SimulateAnomalyTrigger } from "@/shared/components/SimulateAnomalyTrigger";
import { RlPolicyEvaluationBanner } from "@/shared/components/RlPolicyEvaluationBanner";
import { useRemediationStore } from "@/shared/store/remediationStore";
import { useLiveServiceData } from "@/lib/useLiveServiceData";
import { StatCard } from "./components/StatCard";
import { ActionsBarChart } from "./components/ActionsBarChart";
import { AnomalyScoreChart } from "./components/AnomalyScoreChart";
import { ServiceHealthGrid } from "./components/ServiceHealthGrid";
import { IncidentFeed } from "./components/IncidentFeed";
import { DriftAlertBanner } from "./components/DriftAlertBanner";
import { useLiveDashboard } from "./lib/liveDashboard";
import {
  anomalyScoreTrend,
  recoveryActionsByDay,
  statCards,
} from "./data/mockData";

export function DashboardPage() {
  const {
    services: apiServices,
    incidents: apiIncidents,
    loading,
    error,
  } = useLiveServiceData();
  const serviceOverrides = useRemediationStore((s) => s.serviceOverrides);
  const recoveryActionsDelta = useRemediationStore(
    (s) => s.recoveryActionsDelta,
  );
  const liveIncidents = useRemediationStore((s) => s.liveIncidents);
  const live = useLiveDashboard();

  const liveServices = apiServices.map((s) =>
    serviceOverrides[s.serviceId]
      ? { ...s, status: serviceOverrides[s.serviceId], driftDetected: false }
      : s,
  );

  const meanAnomalyScore = liveServices.length
    ? liveServices.reduce((sum, service) => sum + service.anomalyScore, 0) /
      liveServices.length
    : null;
  const liveValues: Record<string, string> = {
    "Active services": String(liveServices.length),
    "Critical incidents": String(
      liveServices.filter((service) => service.status === "critical").length,
    ),
    "Mean anomaly score":
      meanAnomalyScore === null ? "—" : meanAnomalyScore.toFixed(2),
    "Recovery actions today": String(
      Number(statCards[3].value) + recoveryActionsDelta,
    ),
  };
  const liveStatCards = statCards.map((card) => ({
    label: card.label,
    value: liveValues[card.label] ?? card.value,
    deltaLabel:
      card.label === "Recovery actions today" ? "Demo counter" : "Live API",
  }));

  const liveRecoveryActionsByDay =
    recoveryActionsDelta > 0
      ? recoveryActionsByDay.map((d, i) =>
          i === recoveryActionsByDay.length - 1
            ? { ...d, value: d.value + recoveryActionsDelta }
            : d,
        )
      : recoveryActionsByDay;

  const liveIncidentFeed = [...liveIncidents, ...apiIncidents];

  return (
    <AppShell pageTitle="Dashboard">
      <div className="space-y-6">
        {/* ml-backend (Component 1+2) live data wins; otherwise the decision-engine feed below. */}
        {live && <DriftAlertBanner affectedServices={live.driftServices} />}
        {!live && loading && apiServices.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Loading live service data...
          </p>
        )}
        {!live && error && (
          <p
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            Could not refresh live service data: {error}
          </p>
        )}

        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            Simulate an anomaly to see the adaptive decision engine evaluate and
            execute a remediation live.
          </p>
          <SimulateAnomalyTrigger />
        </div>
        <RlPolicyEvaluationBanner />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {(live ? live.statCards : liveStatCards).map((card) => (
            <StatCard key={card.label} {...card} />
          ))}
        </div>

        <div className="grid grid-cols-1 gap-4 rounded-xl border border-border/60 p-4 lg:grid-cols-2">
          <ActionsBarChart data={liveRecoveryActionsByDay} changePct={66.9} />
          {live ? (
            <AnomalyScoreChart
              data={live.trend}
              description="Fleet mean anomaly score, live. Each label is a replay step."
            />
          ) : (
            <AnomalyScoreChart data={anomalyScoreTrend} changePct={58.3} />
          )}
        </div>

        <div className="grid grid-cols-1 gap-6 rounded-xl border border-border/60 p-4 xl:grid-cols-[2fr_1fr]">
          <ServiceHealthGrid services={live ? live.services : liveServices} />
          <IncidentFeed incidents={liveIncidentFeed} />
        </div>
      </div>
    </AppShell>
  );
}
