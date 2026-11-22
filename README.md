# self-healing-framework

A closed-loop reliability system for Kubernetes-hosted microservices. It ingests operational
telemetry, detects anomalies with a per-service streaming ML model, keeps that model correct as the
services change (CADAL, a change-aware model lifecycle with the operator in the loop), and shows all
activity on a real-time React dashboard. Remediation is meant to go through a policy-aware decision
engine and the Kubernetes API.

**New here?** The [setup guide](#setup-guide-step-by-step) takes you from an empty laptop to a running
SHARP, step by step.

## Architecture and DevOps

Everything runs on one Windows laptop (Intel i7-1165G7, 4 cores, 16 GB). Nothing is deployed to a
cloud. Docker Desktop hosts a minikube cluster with Online Boutique, the monitoring stack and
Chaos Mesh. ml-backend (the anomaly detector and the CADAL model lifecycle) runs **inside the
cluster** from its Helm chart, next to what it monitors. It can still run as a host process for
the replay demo.

```mermaid
flowchart TB
    browser([Browser])

    subgraph laptop["Windows laptop: i7-1165G7, 4 cores, 16 GB"]
        subgraph host["Host processes (pnpm, uv)"]
            fe["Frontend<br/>React + Vite :5173"]
            de["decision-engine (FastAPI) :8000"]
        end

        subgraph mk["minikube node, profile sharp: 4 CPU, 7 GB, Kubernetes v1.33.1"]
            subgraph nssh["namespace selfheal-system (Helm chart self-healing-framework)"]
                mlb["ml-backend :8002<br/>PCA detector + CADAL lifecycle<br/>/metrics, /api/ready"]
                ts[("TimescaleDB<br/>StatefulSet, 2 Gi")]
                rd[("Redis<br/>stream + pub/sub")]
            end
            subgraph nsmon["namespace monitoring"]
                prom["Prometheus :9090<br/>5 s scrape, 6 h retention"]
                gf["Grafana :3000"]
                ksm["kube-state-metrics<br/>node-exporter, cAdvisor"]
                bb["blackbox exporter<br/>a request per service every 5 s"]
            end
            subgraph nsob["namespace online-boutique"]
                ob["Online Boutique, 11 services<br/>+ load generator"]
            end
            subgraph nschaos["namespace chaos-testing"]
                cm["Chaos Mesh"]
            end
            kapi["Kubernetes API"]
        end
    end

    browser --> fe
    browser -.->|dashboards| gf
    fe <-->|REST + WebSocket, port-forward :8002| mlb
    mlb --> ts
    mlb --> rd
    rd -.->|planned consumer| de
    mlb -->|PromQL: 8 features per service| prom
    prom -->|ServiceMonitor: /metrics| mlb
    mlb -->|Role: watch rollouts and restarts, run chaos| kapi
    gf -->|PromQL| prom
    ksm --> prom
    bb -->|probe_duration_seconds| prom
    bb -->|gRPC health, HTTP, TCP| ob
    ob -->|container metrics| prom
    cm -->|CPU, memory, pod-kill, network faults| ob
    kapi -.-> cm
```

### What runs where

| Component | Runs as | Reached at | Started by |
|---|---|---|---|
| minikube cluster: Prometheus, Grafana, blackbox exporter, Chaos Mesh, Online Boutique | containerd in one Docker container | 9090, 3000 (port-forward) | `infrastructure/online-boutique/up.ps1` |
| ml-backend, TimescaleDB, Redis | pods in `selfheal-system` (Helm chart) | 8002 (port-forward) | `infrastructure/online-boutique/deploy-sharp.ps1` |
| ml-backend for the replay demo | host process, with the compose stack (TimescaleDB 5433, Redis 6380) | 8002 | `services/ml-backend/README.md` |
| Frontend | host process | 5173 | `pnpm dev` |
| decision-engine | host process | 8000 | `uv run uvicorn app.main:app` |
| llm-copilot | container (`services/llm-copilot/Dockerfile`) | 8004 | its own docker-compose |

### Telemetry path

1. Online Boutique pods run in minikube. cAdvisor and kube-state-metrics expose their CPU, memory,
   network, throttling, restarts and readiness. The blackbox exporter times one real request to
   every service every 5 s (gRPC health check, HTTP or TCP), which makes a network delay visible.
2. Prometheus scrapes them every 5 s. ml-backend queries it with PromQL (`services/ml-backend/app/prom.py`):
   eight features per service.
3. The per-service detector turns the features into one anomaly score, and the CADAL lifecycle decides
   when its model may change. Deployment rollouts and pod restarts reach it as change events from
   the Kubernetes API.
4. Scores, decisions and logs are stored in TimescaleDB, published on a Redis stream, and pushed to the
   React dashboard over a WebSocket. The Model lifecycle page also shows the raw telemetry behind
   each service, with its quarantines and decisions marked.
5. ml-backend exports its own metrics (scoring latency, alarms, quarantines, decisions) at `/metrics`;
   Prometheus scrapes them through a ServiceMonitor and Grafana shows them.
6. Chaos Mesh injects real faults (CPU and memory stress, pod kill, network delay) so detection can be
   measured against ground truth (`services/ml-backend/scripts/chaos_campaign.py`).

### DevOps practices in this repo

- **Containers:** a non-root, read-only-root Python image for ml-backend; Docker Compose for the
  laptop data stack, with healthchecks, named volumes and an init schema.
- **Kubernetes:** our own Helm chart (`infrastructure/helm/self-healing-framework`): a Deployment whose
  readiness waits for the model warm-up, a StatefulSet with a volume, a generated Secret, a
  least-privilege Role in the monitored namespace and a restricted security context (`docs/adr/0009`).
- **CI:** GitHub Actions (`.github/workflows/ci.yml`) runs the pipeline and backend tests, the frontend
  build and `helm lint`, and builds the backend image, pushed to GHCR from main.
- **Observability:** Prometheus with ServiceMonitors for the backend and for blackbox probes, Grafana
  dashboards provisioned as ConfigMaps, retention policies (6 h metrics, 7 days logs).
- **Chaos engineering:** repeatable fault campaigns with recorded ground truth and an evaluation script.
- **Automation:** idempotent PowerShell bring-up, deploy and tear-down (`up.ps1`, `deploy-sharp.ps1`,
  `down.ps1`) and a pre-demo health check (`services/ml-backend/scripts/demo_preflight.py`).
- **Engineering practice:** Conventional Commits, pull requests, decision records in `docs/adr/`.

### Current limits (what is not done yet)

- Only ml-backend is in the Helm chart. The decision engine, gateway and frontend have no templates
  yet, and Terraform is empty. The frontend runs as a dev server.
- CI builds and pushes the image but does not deploy: there is no shared cluster, only minikube.
- ml-backend runs as one replica on purpose (two would make competing lifecycle decisions,
  `docs/adr/0009`). Scaling out means sharding services across replicas.
- The Redis stream consumer in the decision engine is planned.

## Seeing the Prometheus and Grafana dashboards

Prerequisites: Docker Desktop (running), `minikube`, `kubectl`, `helm` 3, and PowerShell. The first run
pulls about 3 GB of images and takes several minutes; later runs reuse them.

```powershell
# 1. Bring up the cluster: minikube, Prometheus + Grafana, blackbox exporter, Chaos Mesh,
#    Online Boutique, port-forwards
powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/up.ps1

# 2. After about an hour of untouched traffic (the model warm-up window), deploy ml-backend with Helm
powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/deploy-sharp.ps1

# 3. Check that everything is running (ml-backend turns Ready once it has warmed up)
kubectl -n monitoring get pods
kubectl -n online-boutique get pods
kubectl -n selfheal-system get pods
```

Then `cd frontend; pnpm dev` and open http://localhost:5173/model-lifecycle.

**Prometheus** at http://localhost:9090

- Status, then Targets: every target should be `UP`.
- Graph tab, try:
  - `sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="online-boutique", container!=""}[1m]))`
  - `kube_deployment_status_replicas_available{namespace="online-boutique"}`
  - `increase(kube_pod_container_status_restarts_total{namespace="online-boutique"}[5m])`
  - `max by (app) (probe_duration_seconds{probe_namespace="online-boutique"})` (response time per service)
  - `sum by (action) (increase(sharp_lifecycle_decisions_total[1h]))` (CADAL decisions, from ml-backend)
  - `histogram_quantile(0.99, sum by (le) (rate(sharp_score_seconds_bucket[5m])))` (per-event scoring time)

**Grafana** at http://localhost:3000, user `admin`. The password is generated by the chart:

```powershell
kubectl -n monitoring get secret kube-prom-grafana -o jsonpath="{.data.admin-password}" | % { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
```

- Dashboards, then **SHARP Online Boutique**: the eight per-service features that the detector consumes,
  with a Service selector (`infrastructure/online-boutique/grafana-dashboard-sharp.yaml`).
- Dashboards, then **SHARP ml-backend: detection and CADAL lifecycle**: anomaly scores, alarm rates,
  quarantines, decisions, model versions and the per-event scoring time against the 5 ms bound
  (from the Helm chart).
- Dashboards, then **Kubernetes / Compute Resources / Namespace (Pods)**, and choose `online-boutique`:
  the stock dashboard that ships with kube-prometheus-stack.

**See a real fault in the dashboards.** With ml-backend deployed, open the Model lifecycle page, and
click **CPU** or **Kill pod** on a service card (see `services/ml-backend/README.md`, "Live mode"). Watch the
CPU or restarts panel in Grafana react, and the anomaly score on the dashboard follow.

If a port-forward has died (for example after a laptop sleep):

```powershell
kubectl --context sharp -n monitoring port-forward svc/kube-prom-grafana 3000:80
kubectl --context sharp -n monitoring port-forward svc/kube-prom-kube-prometheus-prometheus 9090:9090
```

Open the demo shop itself with `minikube service frontend-external -n online-boutique -p sharp`.

Stop everything (keeps images and data): `powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/down.ps1`.
Remove it completely: `minikube delete -p sharp`.

Grafana is limited to 300 MiB in a 7 GB cluster. If the laptop struggles, set `grafana.enabled: false` in
`infrastructure/online-boutique/prometheus-values.yaml` and run `up.ps1` again.

## Layout

| Path | What lives there |
|---|---|
| `services/ml-backend/` | FastAPI backend: telemetry (replay or Prometheus), PCA detector, CADAL lifecycle, REST + WebSocket |
| `services/auth/` | Accounts, organizations and roles (Better Auth); in production also serves the dashboard |
| `services/decision-engine/` | Decision engine (Python/FastAPI): policy evaluation and action dispatch |
| `services/yarp-gateway/` | YARP traffic gateway (planned, README only) |
| `services/llm-copilot/` | LangChain RCA and copilot service |
| `services/shared/` | Cross-service shared code |
| `services/target-services/` | Sample microservices for chaos-injection demos |
| `frontend/` | React 18 + Vite + Tailwind observability dashboard |
| `ml-pipeline/` | Research pipeline: detector, CADAL (dynamic model updating) and their evaluation, see `RESULTS.md` and `RESULTS_COMPONENT2.md` |
| `infrastructure/` | Local compose files, the Online Boutique cluster setup, Helm and Kubernetes manifests |
| `datasets/` | Dataset download scripts (raw data itself is gitignored) |
| `docs/` | Architecture, decision records (`docs/adr/`), execution guide and per-topic docs |

## Accounts, organizations and hosting

SHARP has accounts and multi-tenancy: people sign up, create an organization (a tenant) and invite
teammates as viewer, operator, admin or owner. Each organization gets its own fleet, models,
decisions and logs, and cannot see another's. Accounts run on Better Auth (`services/auth`, free
and self-hosted); ml-backend checks a short-lived JWT on every request. Decisions in
`docs/adr/0014` to `0016`.

The whole application deploys to Render's free plan from `render.yaml`: the dashboard and accounts
in one web service, ml-backend replaying the SMD demo, PostgreSQL and Key Value. Step by step,
with the free plan's limits: [`docs/Deployment_Render.md`](docs/Deployment_Render.md). The live
Online Boutique mode needs Kubernetes and stays on minikube.

## Setup guide (step by step)

This section takes you from an empty laptop to a running SHARP. Follow the steps in order. Every
command is for **PowerShell on Windows** (the project's development machine); on macOS or Linux the
same commands work in a normal terminal.

### Pick how you want to run it

| Way | What you get | You need | First time |
|---|---|---|---|
| **A. Quick demo** | The dashboard with six demo services replaying real server data, and CADAL deciding when models change. No login | Docker, Python, Node | about 15 minutes |
| **B. Demo with accounts** | Way A plus sign up, organizations, roles and invitations | Way A, plus the auth service | 5 more minutes |
| **C. Live Kubernetes** | SHARP watching a real shop (Online Boutique) on a local Kubernetes cluster, with real faults injected | Way A, plus minikube, kubectl and Helm, and about 10 GB of free memory | about 1.5 hours (one hour of it is waiting) |
| **D. On the internet** | A public link anyone can sign up on | GitHub and Render accounts | see [docs/Deployment_Render.md](docs/Deployment_Render.md) |

New to the project? Start with **A**.

### Step 1. Install the tools (once per laptop)

| Tool | Why | Install (Windows) | Check it works |
|---|---|---|---|
| Git | download the code | `winget install Git.Git` | `git --version` |
| Docker Desktop | runs the database and Redis | `winget install Docker.DockerDesktop`, then open Docker Desktop and leave it running | `docker info` |
| uv | runs the Python services (it installs Python 3.11 for you) | `winget install astral-sh.uv` | `uv --version` |
| Node.js 22 | runs the dashboard and the auth service | `winget install OpenJS.NodeJS.LTS` | `node --version` (22 or newer) |
| pnpm 10 | installs the dashboard's packages | `corepack enable` then `corepack prepare pnpm@10.13.1 --activate` | `pnpm --version` |
| *Way C only:* minikube, kubectl, Helm | the local Kubernetes cluster | `winget install Kubernetes.minikube Kubernetes.kubectl Helm.Helm` | `minikube version` |

Close and reopen PowerShell after installing, so it finds the new tools.

### Step 2. Get the code and install its packages

```powershell
git clone https://github.com/SHARPResearch/self-healing-framework.git
cd self-healing-framework

cd services/ml-backend ; uv sync ; cd ../..        # the backend's Python packages
cd frontend ; pnpm install ; cd ..                 # the dashboard's packages
cd services/auth ; npm install ; cd ../..          # only for Way B (accounts)
```

The first `uv sync` downloads Python and the machine learning libraries, so it can take a few minutes.

**Get the demo data (once).** The demo replays the public Server Machine Dataset (SMD), which is
too big to keep in git:

```powershell
bash datasets/smd/download.sh      # Git Bash; or download the dataset by hand, see the script
```

### Step 3. Settings files (`.env`)

A `.env` file holds the settings of one service: addresses, passwords, switches. Each service has a
`.env.example` next to it showing every setting with a safe default. To use one, **copy it to
`.env` in the same folder** and change what you need. `.env` files are ignored by git, so passwords
in them are never uploaded. Never put a real password in a `.env.example`.

| File | Needed for | What to do |
|---|---|---|
| `services/ml-backend/.env` | nothing for Way A (the defaults work) | Copy from `.env.example` only to change something, for example `TELEMETRY_MODE=prometheus` for Way C |
| `services/auth/.env` | Way B | Copy from `.env.example` and set `BETTER_AUTH_SECRET` (below) |
| `frontend/.env` | optional | Copy from `.env.example` if you run the decision engine or copilot on other ports |

**ml-backend** (`services/ml-backend/.env.example`, the most useful lines):

```ini
DATABASE_URL=postgresql://postgres:selfheal@localhost:5433/selfheal   # the demo database
REDIS_URL=redis://localhost:6380
TELEMETRY_MODE=replay        # replay = demo data; prometheus = the live cluster (Way C)
AUTH_MODE=off                # off = no login; jwt = accounts (Way B)
REPLAY_EVENTS_PER_SEC=60     # demo speed
```

**auth service** (`services/auth/.env.example`):

```ini
BETTER_AUTH_SECRET=change-me-to-a-long-random-value
BETTER_AUTH_URL=http://localhost:5173          # the address you open in the browser
DATABASE_URL=postgresql://postgres:selfheal@localhost:5433/selfheal
ML_BACKEND_URL=http://localhost:8002
# RESEND_API_KEY=     optional: send invitation emails; without it, copy invite links from the app
```

Make a random secret with: `-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 40 | % {[char]$_})`

**Dashboard switches.** `VITE_AUTH` can go in `frontend/.env` (copied from its `.env.example`) or be
set in the terminal. The two addresses below it are only read from the terminal: set them in the
same PowerShell window before `pnpm dev`, if you need to change them at all.

| Setting | Meaning |
|---|---|
| `VITE_AUTH=on` (or `$env:VITE_AUTH = "on"`) | show the real sign in pages and use accounts (Way B). Leave empty for Way A |
| `$env:ML_BACKEND_URL = "http://localhost:8002"` | where the dashboard's dev server finds ml-backend (this is the default) |
| `$env:AUTH_URL = "http://localhost:8010"` | where it finds the auth service (this is the default) |

### Way A. Quick demo (no login)

Open **three** PowerShell windows in the project folder.

1. **Start the database and Redis** (window 1). Docker Desktop must be running.
   ```powershell
   docker compose -f infrastructure/local/docker-compose.demo.yml up -d
   ```
   This starts TimescaleDB on port 5433 and Redis on port 6380. Run it once; they keep running in
   the background.

2. **Start ml-backend** (window 2):
   ```powershell
   cd services/ml-backend
   uv run uvicorn app.main:app --port 8002
   ```
   Wait for `Application startup complete`. It first trains one model per demo service, which takes
   about 20 seconds.

3. **Start the dashboard** (window 3):
   ```powershell
   cd frontend
   pnpm dev
   ```

4. **Open http://localhost:5173/model-lifecycle.** You should see six service cards with moving
   score charts, and a green **Live** badge at the top. Click **Deploy** on Orders: within about 30
   seconds CADAL opens a quarantine and promotes a new model. Click **Silent** on Inventory: CADAL
   asks you "new normal or incident?".

Check that the backend is healthy at any time: open http://localhost:8002/api/health. It should
say `"status":"ok"` and `"db":true`.

### Way B. Demo with accounts

Do Step 3 for `services/auth/.env` first. Then use **four** windows:

1. Database and Redis, as in Way A step 1.
2. **Auth service:**
   ```powershell
   cd services/auth
   npm run dev
   ```
   It creates its tables the first time and listens on port 8010.
3. **ml-backend with accounts on:**
   ```powershell
   cd services/ml-backend
   $env:AUTH_MODE = "jwt"
   uv run uvicorn app.main:app --port 8002
   ```
4. **Dashboard with accounts on:**
   ```powershell
   cd frontend
   $env:VITE_AUTH = "on"
   pnpm dev
   ```
5. Open **http://localhost:5173/signup**, create an account, then create your organization. You
   land on the Model lifecycle page with your own demo fleet. To add a teammate, open
   **Organization** in the sidebar, enter their email and a role, and send them the link it shows.

| Role | Can do |
|---|---|
| viewer | see everything in the organization |
| operator | also answer CADAL's questions and run checks and demo actions |
| admin | also promote or roll back models, reset the fleet, manage members |
| owner | everything, including deleting the organization |

### Way C. Live Kubernetes (Online Boutique)

This runs a real online shop on a local Kubernetes cluster and lets SHARP watch it. It needs about
10 GB of free memory; close heavy programs first.

1. **Start the cluster** (the first run downloads about 3 GB):
   ```powershell
   powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/up.ps1
   ```
   It installs Prometheus and Grafana (monitoring), a probe that measures every service's response
   time, Chaos Mesh (fault injection) and Online Boutique, then opens Prometheus on port 9090 and
   Grafana on port 3000.
2. **Wait about one hour without touching it.** SHARP learns what "normal" looks like from the
   last hour of the shop's traffic, so that hour must be calm.
3. **Deploy SHARP into the cluster:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/deploy-sharp.ps1
   ```
   This builds the ml-backend image, installs it with its Helm chart and opens it on port 8002.
4. **Start the dashboard** as in Way A step 3 and open http://localhost:5173/model-lifecycle. You
   now see the shop's 11 real services. **CPU** and **Kill pod** inject real faults; the
   **Telemetry evidence** panel under the cards shows the raw metrics behind each decision.
5. **Grafana:** http://localhost:3000, user `admin`. Get the password with:
   ```powershell
   kubectl -n monitoring get secret kube-prom-grafana -o jsonpath="{.data.admin-password}" | % { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
   ```
   Open the dashboards **SHARP Online Boutique** (the shop's metrics) and **SHARP ml-backend**
   (SHARP's own scoring and decisions).

Keep the laptop plugged in and awake while the cluster runs; if it sleeps, the cluster stops.

### Way D. On the internet (Render)

Everything above runs on your laptop only. To get a public link, follow
[docs/Deployment_Render.md](docs/Deployment_Render.md): it deploys the dashboard, accounts and the
demo to Render's free plan from `render.yaml`. You can rehearse it on the laptop first with
`docker compose -f infrastructure/local/docker-compose.render.yml up -d --build` and
http://localhost:18080.

### Stopping everything

| To stop | Do |
|---|---|
| ml-backend, the auth service, the dashboard | press `Ctrl+C` in their windows |
| the database and Redis (data is kept) | `docker compose -f infrastructure/local/docker-compose.demo.yml down` |
| the database and Redis, deleting their data | add `-v` to the line above |
| the Kubernetes cluster (data is kept) | `powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/down.ps1` |
| the cluster, deleting it completely | `minikube delete -p sharp` |

### If something goes wrong

| What you see | Why | Fix |
|---|---|---|
| The page says "Connecting to ml-backend…" or "ml-backend is not running" | ml-backend is not running, or still starting | Start it (Way A step 2) and wait for `Application startup complete`; the page reconnects by itself |
| `/api/health` shows `"db": false` | the database is not running | Start Docker Desktop, then Way A step 1 |
| `port is already allocated` or `address already in use` | something else uses that port (often an old copy of the same service) | Close the other window, or find it with `Get-NetTCPConnection -LocalPort 8002` |
| `FileNotFoundError ... download.sh` | the demo data is missing | Run `bash datasets/smd/download.sh` (Step 2) |
| Sign in pages send you back to sign in (Way B) | ml-backend is not in `AUTH_MODE=jwt`, or the auth service is not running | Check windows 2 and 3 of Way B |
| `docker` commands fail | Docker Desktop is not running | Open Docker Desktop and wait until it says it is running |
| Way C: services alarm all the time | the warm-up hour was not calm (the cluster had just started, or faults were injected) | Wait another calm hour, then run `deploy-sharp.ps1` again |

More detail on each part: [services/ml-backend/README.md](services/ml-backend/README.md) (the
backend and the demo), [services/auth/README.md](services/auth/README.md) (accounts) and
[infrastructure/README.md](infrastructure/README.md) (the cluster).

## Docs

- `docs/Doc1_Technical_Architecture.md`: architecture, data flow, ML config, decision policy
- `docs/Doc2_GitHub_Monorepo_Structure.md`: the folder layout this repo follows
- `docs/Doc3_Execution_Guide.md`: chronological build phases
- `docs/Component_2_Dynamic_Model_Updating.md`: research positioning and design of CADAL
- `docs/adr/`: decision records (detector choice, attribute before acting, early stop, restarts,
  deployment, accounts and tenancy)
- `docs/Deployment_Render.md`: deploying the application to Render's free plan
