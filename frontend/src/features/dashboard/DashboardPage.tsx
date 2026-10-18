import { AppShell } from "@/shared/layout/AppShell";
import { SimulateAnomalyTrigger } from "@/shared/components/SimulateAnomalyTrigger";
import { RlPolicyEvaluationBanner } from "@/shared/components/RlPolicyEvaluationBanner";
import { useRemediationStore } from "@/shared/store/remediationStore";
import { StatCard } from "./components/StatCard";
import { ActionsBarChart } from "./components/ActionsBarChart";
import { AnomalyScoreChart } from "./components/AnomalyScoreChart";
import { ServiceHealthGrid } from "./components/ServiceHealthGrid";
import { IncidentFeed } from "./components/IncidentFeed";
import { DriftAlertBanner } from "./components/DriftAlertBanner";
import { useLiveDashboard } from "./lib/liveDashboard";
import {
  anomalyScoreTrend,
  driftAlertServices,
  recentIncidents,
  recoveryActionsByDay,
  services,
  statCards,
} from "./data/mockData";

// Mock-typical score for a service once a simulated remediation resolves it
// back to "watch" -- matches the range the other watch-status services in
// mockData.ts already sit in (0.08-0.15).
const RESOLVED_SCORE = 0.12;

export function DashboardPage() {
  const serviceOverrides = useRemediationStore((s) => s.serviceOverrides);
  const recoveryActionsDelta = useRemediationStore((s) => s.recoveryActionsDelta);
  const liveIncidents = useRemediationStore((s) => s.liveIncidents);
  const live = useLiveDashboard();

  const liveServices = services.map((s) =>
    serviceOverrides[s.serviceId] ? { ...s, status: serviceOverrides[s.serviceId], driftDetected: false } : s,
  );

  const liveStatCards = statCards.map((card) =>
    card.label === "Recovery actions today" && recoveryActionsDelta > 0
      ? { ...card, value: String(Number(card.value) + recoveryActionsDelta) }
      : card,
  );

  const liveRecoveryActionsByDay =
    recoveryActionsDelta > 0
      ? recoveryActionsByDay.map((d, i) =>
          i === recoveryActionsByDay.length - 1 ? { ...d, value: d.value + recoveryActionsDelta } : d,
        )
      : recoveryActionsByDay;

  const liveAnomalyScoreTrend =
    recoveryActionsDelta > 0
      ? [
          ...anomalyScoreTrend,
          {
            label: "Now",
            score: Number(
              (
                liveServices.reduce(
                  (sum, s) => sum + (serviceOverrides[s.serviceId] ? RESOLVED_SCORE : s.anomalyScore),
                  0,
                ) / liveServices.length
              ).toFixed(2),
            ),
          },
        ]
      : anomalyScoreTrend;

  const liveIncidentFeed = [...liveIncidents, ...recentIncidents];

  return (
    <AppShell pageTitle="Dashboard">
      <div className="space-y-6">
        <DriftAlertBanner affectedServices={live ? live.driftServices : driftAlertServices} />

        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            Simulate an anomaly to see the adaptive decision engine evaluate and execute a
            remediation live.
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
            <AnomalyScoreChart data={liveAnomalyScoreTrend} changePct={58.3} />
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
