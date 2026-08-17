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
import { ModelsPage } from "@/features/models/ModelsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { NotFoundPage } from "@/shared/components/NotFoundPage";
import { ProfilePage } from "@/features/profile/ProfilePage";

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
      <Route path="/models" element={<ModelsPage />} />
      <Route path="/copilot" element={<CopilotPage />} />
      <Route path="/notifications" element={<NotificationsPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export default App;
