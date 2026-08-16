import { AppShell } from "@/shared/layout/AppShell";
import { IncidentReportCard } from "./components/IncidentReportCard";

export function IncidentsPage() {
  return (
    <AppShell pageTitle="Incidents">
      <IncidentReportCard />
    </AppShell>
  );
}
