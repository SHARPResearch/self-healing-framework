import { Navigate, Route, Routes } from "react-router-dom";
import { LoginPage } from "@/features/auth/LoginPage";
import { SignupPage } from "@/features/auth/SignupPage";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { CopilotPage } from "@/features/copilot/CopilotPage";
import { IncidentsPage } from "@/features/incidents/IncidentsPage";
import { ServicesPage } from "@/features/services/ServicesPage";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";
import { DependencyGraphPage } from "@/features/dependency-graph/DependencyGraphPage";
import { AppShell } from "@/shared/layout/AppShell";
import { ComingSoonPage } from "@/shared/components/ComingSoonPage";
import { NotFoundPage } from "@/shared/components/NotFoundPage";
import { ProfilePage } from "@/features/profile/ProfilePage";

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
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/services" element={<ServicesPage />} />
      <Route path="/dependency-graph" element={<DependencyGraphPage />} />
      <Route path="/incidents" element={<IncidentsPage />} />
      <Route path="/models" element={<StubRoute title="Models" />} />
      <Route path="/copilot" element={<CopilotPage />} />
      <Route path="/notifications" element={<NotificationsPage />} />
      <Route path="/settings" element={<StubRoute title="Settings" />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export default App;
