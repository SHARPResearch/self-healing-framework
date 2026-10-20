import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { LoginPage } from "@/features/auth/LoginPage";
import { SignupPage } from "@/features/auth/SignupPage";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { IncidentsPage } from "@/features/incidents/IncidentsPage";
import { ServicesPage } from "@/features/services/ServicesPage";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";
import { ModelsPage } from "@/features/models/ModelsPage";
import { ModelLifecyclePage } from "@/features/lifecycle/ModelLifecyclePage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { NotFoundPage } from "@/shared/components/NotFoundPage";
import { ProfilePage } from "@/features/profile/ProfilePage";
import { RouteFallback } from "@/shared/components/RouteFallback";
import { AnomalyListPage } from "@/features/anomalies/AnomalyListPage";
import { DecisionListPage } from "@/features/decisions/DecisionListPage";

/**
 * Lazy loaded so their weight stays out of the shared bundle: marketing pulls
 * a background video, dependency-graph pulls d3-force, and copilot is the
 * heaviest framer-motion user. The .then wrapper preserves the named-export
 * convention every page in features/ follows.
 */
const MarketingPage = lazy(() =>
  import("@/features/marketing/MarketingPage").then((m) => ({
    default: m.MarketingPage,
  })),
);
const DependencyGraphPage = lazy(() =>
  import("@/features/dependency-graph/DependencyGraphPage").then((m) => ({
    default: m.DependencyGraphPage,
  })),
);
const CopilotPage = lazy(() =>
  import("@/features/copilot/CopilotPage").then((m) => ({
    default: m.CopilotPage,
  })),
);

function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/" element={<MarketingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/services" element={<ServicesPage />} />
        <Route path="/dependency-graph" element={<DependencyGraphPage />} />
        <Route path="/anomalies" element={<AnomalyListPage />} />
        <Route path="/decisions" element={<DecisionListPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/model-lifecycle" element={<ModelLifecyclePage />} />
        <Route path="/copilot" element={<CopilotPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}

export default App;
