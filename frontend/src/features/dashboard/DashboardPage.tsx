import { AppShell } from "@/shared/layout/AppShell";
import { StatCard } from "./components/StatCard";
import { ActionsBarChart } from "./components/ActionsBarChart";
import { AnomalyScoreChart } from "./components/AnomalyScoreChart";
import { ServiceHealthGrid } from "./components/ServiceHealthGrid";
import { IncidentFeed } from "./components/IncidentFeed";
import { DriftAlertBanner } from "./components/DriftAlertBanner";
import {
  anomalyScoreTrend,
  driftAlertServices,
  recentIncidents,
  recoveryActionsByDay,
  services,
  statCards,
} from "./data/mockData";

export function DashboardPage() {
  return (
    <AppShell pageTitle="Dashboard">
      <div className="space-y-6">
        <DriftAlertBanner affectedServices={driftAlertServices} />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {statCards.map((card) => (
            <StatCard key={card.label} {...card} />
          ))}
        </div>

        <div className="grid grid-cols-1 gap-4 rounded-xl border border-border/60 p-4 lg:grid-cols-2">
          <ActionsBarChart data={recoveryActionsByDay} changePct={66.9} />
          <AnomalyScoreChart data={anomalyScoreTrend} changePct={58.3} />
        </div>

        <div className="grid grid-cols-1 gap-6 rounded-xl border border-border/60 p-4 xl:grid-cols-[2fr_1fr]">
          <ServiceHealthGrid services={services} />
          <IncidentFeed incidents={recentIncidents} />
        </div>
      </div>
    </AppShell>
  );
}
