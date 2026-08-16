import { Navigate, Route, Routes } from "react-router-dom";
import { LoginStubPage } from "@/features/auth/LoginStubPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { CopilotPage } from "@/features/copilot/CopilotPage";
import { AppShell } from "@/shared/layout/AppShell";
import { ComingSoonPage } from "@/shared/components/ComingSoonPage";

function StubRoute({ title }: { title: string }) {
  return (
    <AppShell pageTitle={title}>
      <ComingSoonPage title={title} />
    </AppShell>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<LoginStubPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/services" element={<StubRoute title="Services" />} />
      <Route path="/dependency-graph" element={<StubRoute title="Dependency graph" />} />
      <Route path="/incidents" element={<StubRoute title="Incidents" />} />
      <Route path="/models" element={<StubRoute title="Models" />} />
      <Route path="/copilot" element={<CopilotPage />} />
      <Route path="/settings" element={<StubRoute title="Settings" />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
