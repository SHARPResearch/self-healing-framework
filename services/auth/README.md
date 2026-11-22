# auth (SHARP web server)

Accounts, organizations and roles for SHARP, with [Better Auth](https://www.better-auth.com)
(free, self-hosted, data in our own PostgreSQL). In production this one Node server is also what
the browser talks to: it serves the dashboard, answers `/api/auth`, and forwards `/api` and `/ws`
to ml-backend. Decisions: `docs/adr/0014` to `0016`.

| Path | What |
|---|---|
| `/api/auth/*` | Better Auth: sign up, sign in, sessions, organizations, invitations, `/token` (a 15 minute JWT for ml-backend), `/jwks` (its public key) |
| `/api/*`, `/ws/*` | proxied to `ML_BACKEND_URL`; ml-backend checks the JWT itself |
| `/healthz` | 200 when the database answers |
| everything else | the dashboard from `STATIC_DIR` (production image only) |

## Roles

An organization is a tenant: ml-backend gives it its own fleet and data. Members have one role:

| Role | SHARP permissions |
|---|---|
| viewer | read |
| operator | read, operate (answer CADAL queries, checks, demo and live actions) |
| admin | read, operate, manage (promote, roll back, reset; invite and manage members) |
| owner | as admin, plus delete the organization |

The JWT carries `sub`, `email`, `org` (the active organization) and `role`. The same roles are
declared in `frontend/src/lib/auth.ts`; keep the two in step.

## Run locally

```powershell
docker compose -f infrastructure/local/docker-compose.demo.yml up -d   # PostgreSQL on 5433
cd services/auth
copy .env.example .env            # then set BETTER_AUTH_SECRET
npm install
npm run dev                       # :8010; creates its tables on first start

# ml-backend with accounts on (second terminal)
cd services/ml-backend
$env:AUTH_MODE="jwt"; uv run uvicorn app.main:app --port 8002

# the dashboard with accounts on (third terminal); Vite proxies /api/auth to :8010
cd frontend
$env:VITE_AUTH="on"; pnpm dev     # http://localhost:5173/signup
```

`AUTH_URL=http://localhost:8010 npm test` runs the end-to-end check against the running server:
sign up, create an organization, invite a viewer, and the JWT claims for each.

## Configuration

| Variable | Default | |
|---|---|---|
| `BETTER_AUTH_SECRET` | (required in production) | signs sessions; Render generates it |
| `BETTER_AUTH_URL` | `RENDER_EXTERNAL_URL`, else `http://localhost:5173` | the browser's origin; also the JWT issuer |
| `DATABASE_URL` | the local compose database | PostgreSQL |
| `DATABASE_SSL` | `false` | `true` for an external database that requires TLS |
| `ML_BACKEND_URL` | `http://localhost:8002` | where `/api` and `/ws` go |
| `TRUSTED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | extra origins allowed to call `/api/auth` |
| `JWT_AUDIENCE` | `sharp-ml-backend` | must match ml-backend's `AUTH_AUDIENCE` |
| `RESEND_API_KEY`, `EMAIL_FROM` | unset | send invitation and reset emails; otherwise they are logged |
| `STATIC_DIR` | unset | serve the built dashboard from here (the image sets `public`) |
| `PORT` | `8010` | Render sets it |
