/**
 * Better Auth for SHARP: email and password accounts, organizations (the tenants), four roles,
 * invitations, and short-lived JWTs that ml-backend verifies against /api/auth/jwks.
 *
 * Tenancy: every organization is a tenant. ml-backend scopes all its data (fleet, decisions,
 * queries, logs) to the `org` claim of the JWT, and checks the `role` claim before an action.
 *
 *   role      can                                                          (sharp permission)
 *   viewer    see the dashboards                                           read
 *   operator  + answer CADAL queries, run checks and live actions          read, operate
 *   admin     + promote / roll back models, reset; invite and manage members  read, operate, manage
 *   owner     + delete the organization                                     read, operate, manage
 *
 * Free and self-hosted: the data lives in our own Postgres (DATABASE_URL). Email is optional:
 * without RESEND_API_KEY, invitation and password reset links are logged and the dashboard shows
 * the invitation link to copy.
 */
import { betterAuth } from "better-auth";
import { jwt, organization } from "better-auth/plugins";
import { createAccessControl } from "better-auth/plugins/access";
import { adminAc, defaultStatements, ownerAc } from "better-auth/plugins/organization/access";
import pg from "pg";

// The browser's origin. Render sets RENDER_EXTERNAL_URL (https://<service>.onrender.com) itself.
export const PUBLIC_URL = process.env.BETTER_AUTH_URL ?? process.env.RENDER_EXTERNAL_URL ?? "http://localhost:5173";
export const JWT_AUDIENCE = process.env.JWT_AUDIENCE ?? "sharp-ml-backend";
const TRUSTED = [PUBLIC_URL, ...(process.env.TRUSTED_ORIGINS ?? "http://localhost:5173,http://127.0.0.1:5173")
  .split(",").map((s) => s.trim()).filter(Boolean)];

export const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL ?? "postgresql://postgres:selfheal@localhost:5433/selfheal",
  // Render's managed Postgres requires TLS; the local compose database has none
  ssl: process.env.DATABASE_SSL === "true" ? { rejectUnauthorized: false } : undefined,
  max: 5,
});

// -- roles --------------------------------------------------------------------------------------
const statements = { ...defaultStatements, sharp: ["read", "operate", "manage"] };
export const ac = createAccessControl(statements);
export const roles = {
  owner: ac.newRole({ ...ownerAc.statements, sharp: ["read", "operate", "manage"] }),
  admin: ac.newRole({ ...adminAc.statements, sharp: ["read", "operate", "manage"] }),
  operator: ac.newRole({ sharp: ["read", "operate"] }),
  viewer: ac.newRole({ sharp: ["read"] }),
};

// -- email (optional) ---------------------------------------------------------------------------
async function sendEmail(to, subject, text) {
  const key = process.env.RESEND_API_KEY;
  if (!key) {
    console.log(`[email not configured] to ${to}: ${subject}\n${text}`);
    return;
  }
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: process.env.EMAIL_FROM ?? "SHARP <onboarding@resend.dev>", to, subject, text }),
  });
  if (!res.ok) console.error(`email to ${to} failed: ${res.status} ${await res.text()}`);
}

async function roleOf(userId, organizationId) {
  if (!organizationId) return null;
  const { rows } = await pool.query(
    'SELECT role FROM "member" WHERE "userId" = $1 AND "organizationId" = $2 LIMIT 1',
    [userId, organizationId],
  );
  return rows[0]?.role ?? null;
}

async function firstOrganization(userId) {
  const { rows } = await pool.query(
    'SELECT "organizationId" FROM "member" WHERE "userId" = $1 ORDER BY "createdAt" LIMIT 1',
    [userId],
  );
  return rows[0]?.organizationId ?? null;
}

export const auth = betterAuth({
  appName: "SHARP",
  baseURL: PUBLIC_URL,
  secret: process.env.BETTER_AUTH_SECRET,
  database: pool,
  trustedOrigins: TRUSTED,
  emailAndPassword: {
    enabled: true,
    minPasswordLength: 8,
    sendResetPassword: async ({ user, url }) => {
      await sendEmail(user.email, "Reset your SHARP password", `Reset your password: ${url}`);
    },
  },
  databaseHooks: {
    session: {
      create: {
        // open every new session on the user's first organization, so the dashboard has a tenant
        before: async (session) => ({
          data: { ...session, activeOrganizationId: await firstOrganization(session.userId) },
        }),
      },
    },
  },
  plugins: [
    organization({
      ac,
      roles,
      creatorRole: "owner",
      invitationExpiresIn: 7 * 24 * 3600,
      sendInvitationEmail: async ({ email, id, organization: org, inviter, role }) => {
        const link = `${PUBLIC_URL}/accept-invitation/${id}`;
        await sendEmail(email, `Join ${org.name} on SHARP`,
          `${inviter.user.name} invited you to ${org.name} as ${role}. Accept: ${link}`);
      },
    }),
    jwt({
      jwt: {
        issuer: PUBLIC_URL,
        audience: JWT_AUDIENCE,
        expirationTime: "15m",
        // the tenant and the member's role in it: everything ml-backend needs to scope and authorize
        definePayload: async ({ user, session }) => ({
          email: user.email,
          name: user.name,
          org: session.activeOrganizationId ?? null,
          role: await roleOf(user.id, session.activeOrganizationId),
        }),
      },
    }),
  ],
});
