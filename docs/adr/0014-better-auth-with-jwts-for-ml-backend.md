# 0014. Accounts with Better Auth; ml-backend verifies short-lived JWTs

Date: 2026-11-22. Status: Accepted.

## Context
SHARP had no accounts: the sign-in pages were mock-ups, and anyone who could reach ml-backend could
promote or roll back models and answer CADAL's operator questions in anyone's name (the operator
was a text box). Deploying it publicly needs real accounts, organizations as tenants, and roles,
at no cost.

## Decision
- **Better Auth** (`services/auth`, MIT, self-hosted) with email and password, the organization
  plugin (organizations, members, invitations) and the JWT plugin. Its data lives in our own
  PostgreSQL. Four roles: viewer, operator, admin, owner, mapped to three SHARP permissions:
  `read`, `operate` (answer queries, checks, demo and live actions), `manage` (promote, roll back,
  reset, members).
- **ml-backend never sees the session.** The dashboard fetches a 15 minute JWT (Ed25519) from
  `/api/auth/token`; its `org` and `role` claims carry the active organization and the user's role
  in it. ml-backend verifies signature, issuer, audience and expiry against the public JWKS
  (`app/auth.py`, PyJWT) and checks the permission before every handler. The WebSocket takes the
  token as its first message, so it never appears in a URL or an access log.
- The audit trail records the token's email as the operator; the client can no longer name one.
- `AUTH_MODE=off` (the default) keeps the laptop demo and the tests as they were: one implicit
  owner of tenant "default". The dashboard turns accounts on with `VITE_AUTH=on` at build time.

## Alternatives considered
- **Clerk.** Fastest to integrate and has organizations, but the free tier has user and
  organization caps, the data lives with the vendor, and leaving it later means migrating users.
- **Supabase Auth.** Free tier pauses inactive projects, and organizations and roles would be our
  own tables on top of it, which is most of the work anyway.
- **Keycloak.** Free and complete, but a JVM server needing more memory than a free instance has.
- **Sessions checked by ml-backend directly** (cookie forwarded, session looked up in the auth
  tables). Rejected: it couples the Python service to Better Auth's schema and to the database on
  every request; a JWT is verified locally with a cached key.

## Consequences
A stolen token is usable for at most 15 minutes, and a role change takes effect when the next
token is minted. The roles are defined twice (`services/auth/src/auth.js` and
`frontend/src/lib/auth.ts`) and must stay in step; ml-backend only knows the role names. Email is
optional: without a provider, invitation links are copied from the dashboard.
