import { createAuthClient } from "better-auth/react";
import { jwtClient, organizationClient } from "better-auth/client/plugins";
import { createAccessControl } from "better-auth/plugins/access";
import { adminAc, defaultStatements, ownerAc } from "better-auth/plugins/organization/access";

/**
 * Sign-in, organizations (tenants) and the JWT ml-backend checks (services/auth, docs/adr/0014).
 *
 * Off unless the build sets VITE_AUTH=on (the Render deployment does). Off, the dashboard talks to
 * an ml-backend running AUTH_MODE=off exactly as before: no login, one implicit organization.
 *
 * The auth service shares the dashboard's origin (/api/auth: the Vite proxy locally, the SHARP web
 * server in production), so its session cookie is first-party. ml-backend never sees that cookie:
 * it gets a 15 minute JWT, fetched from /api/auth/token and cached here until shortly before it
 * expires. Switching organization drops the cached token, because the token names the tenant.
 */
export const AUTH_ENABLED = import.meta.env.VITE_AUTH === "on";

// The same roles the auth service defines (services/auth/src/auth.js); keep the two in step.
const ac = createAccessControl({ ...defaultStatements, sharp: ["read", "operate", "manage"] });
const roles = {
  owner: ac.newRole({ ...ownerAc.statements, sharp: ["read", "operate", "manage"] }),
  admin: ac.newRole({ ...adminAc.statements, sharp: ["read", "operate", "manage"] }),
  operator: ac.newRole({ sharp: ["read", "operate"] }),
  viewer: ac.newRole({ sharp: ["read"] }),
};

export const authClient = createAuthClient({
  plugins: [organizationClient({ ac, roles }), jwtClient()],
});

export const { useSession, signIn, signUp, signOut } = authClient;

export type Role = "owner" | "admin" | "operator" | "viewer";
export const ROLES: Role[] = ["viewer", "operator", "admin", "owner"];
export const ROLE_HINT: Record<Role, string> = {
  viewer: "Sees dashboards, models and logs",
  operator: "Also answers CADAL questions, runs checks and live actions",
  admin: "Also promotes and rolls back models, resets fleets, manages members",
  owner: "Everything, including deleting the organization",
};

let cached: { token: string; expiresAt: number } | null = null;
let inflight: Promise<string | null> | null = null;

function expiry(token: string): number {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return Number(payload.exp) * 1000;
  } catch {
    return 0;
  }
}

/** A valid JWT for ml-backend, or null when signed out (or when auth is off). */
export async function getAccessToken(): Promise<string | null> {
  if (!AUTH_ENABLED) return null;
  if (cached && cached.expiresAt - Date.now() > 60_000) return cached.token;
  inflight ??= authClient
    .token()
    .then(({ data }) => {
      const token = data?.token ?? null;
      cached = token ? { token, expiresAt: expiry(token) } : null;
      return token;
    })
    .catch(() => null)
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

export function clearAccessToken(): void {
  cached = null;
}

/** Make another organization active, then reload so every view and the live stream follow it. */
export async function switchOrganization(organizationId: string): Promise<void> {
  await authClient.organization.setActive({ organizationId });
  clearAccessToken();
  window.location.assign("/dashboard");
}

export async function logOut(): Promise<void> {
  clearAccessToken();
  await signOut();
  window.location.assign("/login");
}
