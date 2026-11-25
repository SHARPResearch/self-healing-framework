import { Navigate, Outlet, useLocation } from "react-router-dom";
import { AUTH_ENABLED, useSession } from "@/lib/auth";
import { RouteFallback } from "./RouteFallback";

/**
 * Guards every dashboard route when accounts are on: signed out goes to sign in (and comes back),
 * signed in without an organization goes to create or join one. Every page works on the active
 * organization's data only, so there is nothing to show before one exists.
 */
export function RequireAuth() {
  return AUTH_ENABLED ? <SignedIn /> : <Outlet />;
}

function SignedIn() {
  const { data, isPending } = useSession();
  const location = useLocation();
  if (isPending) return <RouteFallback />;
  if (!data) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (!data.session.activeOrganizationId) return <Navigate to="/onboarding" replace />;
  return <Outlet />;
}
