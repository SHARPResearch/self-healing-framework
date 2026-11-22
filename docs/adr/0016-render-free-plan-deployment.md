# 0016. Hosted deployment on Render's free plan: one web origin, replay mode, optional TimescaleDB

Date: 2026-11-22. Status: Accepted.

## Context
Everything ran on one laptop. The team needs a public URL that costs nothing, where people sign
in and see the component working. Render's free plan has no Kubernetes, sleeps idle services,
gives 512 MB per instance, does not let free services receive private network traffic, and
offers PostgreSQL without TimescaleDB.

## Decision
- **Two Docker web services, from `render.yaml`:** `sharp-web` (the dashboard and Better Auth in
  one Node server) and `sharp-ml-backend` (replay mode), with Render PostgreSQL and Key Value.
- **One origin for the browser.** `sharp-web` serves the dashboard, answers `/api/auth`, and
  forwards `/api` and `/ws` to ml-backend. The session cookie is first-party; two
  `*.onrender.com` hosts are different sites, and browsers block third-party cookies. The proxy
  uses ml-backend's public URL, which is why ml-backend verifies the JWT itself rather than
  trusting the proxy.
- **Replay mode on Render.** The live mode needs Prometheus, the Kubernetes API and Chaos Mesh,
  which stay on minikube (0009). The Render image bakes in the three SMD machines the demo
  replays (`Dockerfile.render`).
- **TimescaleDB becomes optional.** The schema creates hypertables and retention policies only
  where the extension exists; on plain PostgreSQL the backend deletes rows past the same
  retention itself (6 hours of scores, 7 days of logs), and queries use `date_trunc` instead of
  `time_bucket`.

## Alternatives considered
- **A static site for the dashboard plus a separate auth service.** Free and simple, but the
  cookie is then cross-site; Better Auth's bearer mode would work at the cost of keeping the
  session token in browser storage.
- **Fly.io, Railway, Koyeb.** No lasting free tier for two services and a database at the time of
  writing, or a card required.
- **Kubernetes on a cloud free tier (e.g. Oracle Cloud's always-free ARM VMs).** Would run the
  live mode, but needs much more setup and maintenance than the project can carry.

## Consequences
The hosted SHARP shows the replay demo, accounts and tenancy; the live cluster results come from
the laptop. Free-plan limits (sleep, 750 hours, the database expiring after 30 days) are listed
with their effects in `docs/Deployment_Render.md`. `infrastructure/local/docker-compose.render.yml`
rehearses the deployment on the laptop with the same images and plain PostgreSQL.
