import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { RequireAuth } from "@/shared/components/RequireAuth";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { OnboardingPage } from "@/features/organization/OnboardingPage";
import { AcceptInvitationPage } from "@/features/organization/AcceptInvitationPage";
import { OrganizationPage } from "@/features/organization/OrganizationPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { SignupPage } from "@/features/auth/SignupPage";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { IncidentsPage } from "@/features/incidents/IncidentsPage";
import { ServicesPage } from "@/features/services/ServicesPage";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";
import { ModelsPage } from "@/features/models/ModelsPage";
import { ModelLifecyclePage } from "@/features/lifecycle/ModelLifecyclePage";
import { LogsPage } from "@/features/logs/LogsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { NotFoundPage } from "@/shared/components/NotFoundPage";
import { ProfilePage } from "@/features/profile/ProfilePage";
import { RouteFallback } from "@/shared/components/RouteFallback";
import { AnomalyListPage } from "@/features/anomalies/AnomalyListPage";
import { PostMortemsPage } from "@/features/copilot/PostMortemsPage";
import { DecisionRunPage } from "@/features/decisions/DecisionRunPage";
import { EscalationsPage } from "@/features/escalations/EscalationsPage";
import { ShadowPage } from "@/features/shadow/ShadowPage";
import { ExecutionsPage } from "@/features/executions/ExecutionsPage";
import { DecisionListPage } from "@/features/decisions/DecisionListPage";
import { DecisionEnginePage } from "@/features/decisions/DecisionEnginePage";
import { RuleListPage } from "@/features/rules/RuleListPage";
import { RuleDetailPage } from "@/features/rules/RuleDetailPage";

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
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/accept-invitation/:id" element={<AcceptInvitationPage />} />
        {/* every page below shows one organization's data: signed in, with an organization */}
        <Route element={<RequireAuth />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/services" element={<ServicesPage />} />
        <Route path="/decision-engine" element={<DecisionEnginePage />} />
        <Route path="/dependency-graph" element={<DependencyGraphPage />} />
        <Route path="/anomalies" element={<AnomalyListPage />} />
        <Route path="/decisions" element={<DecisionListPage />} />
        <Route path="/decisions/:decisionId" element={<DecisionRunPage />} />
        <Route path="/executions" element={<ExecutionsPage />} />
        <Route path="/shadow" element={<ShadowPage />} />
        <Route path="/escalations" element={<EscalationsPage />} />
        <Route path="/rules" element={<RuleListPage />} />
        <Route path="/rules/:id" element={<RuleDetailPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/model-lifecycle" element={<ModelLifecyclePage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/copilot" element={<CopilotPage />} />
        <Route path="/post-mortems" element={<PostMortemsPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/organization" element={<OrganizationPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}

export default App;
