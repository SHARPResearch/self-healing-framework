import { AppShell } from "@/shared/layout/AppShell";
import { ServiceManagementTable } from "./components/ServiceManagementTable";

export function ServicesPage() {
  return (
    <AppShell pageTitle="Services">
      <ServiceManagementTable />
    </AppShell>
  );
}
