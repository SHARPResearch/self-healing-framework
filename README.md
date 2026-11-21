# self-healing-framework

A closed-loop reliability system for Kubernetes-hosted microservices. It ingests operational
telemetry, detects anomalies with a per-service streaming ML model, keeps that model correct as the
services change (CADAL, a change-aware model lifecycle with the operator in the loop), and shows all
activity on a real-time React dashboard. Remediation is meant to go through a policy-aware decision
engine and the Kubernetes API.

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

## Getting started

Quick start for the dynamic model updating demo (replay mode, no Kubernetes needed):

```powershell
docker compose -f infrastructure/local/docker-compose.demo.yml up -d          # TimescaleDB :5433, Redis :6380
cd services/ml-backend ; uv run uvicorn app.main:app --port 8002              # backend
cd frontend ; pnpm dev                                                         # http://localhost:5173
```

`services/ml-backend/README.md` is the runbook for both modes: the replay demo and live Kubernetes.

`make dev` starts the generic Redis and TimescaleDB stack from the root `docker-compose.yml` (ports 6379
and 5432). `docs/Doc3_Execution_Guide.md` has the phased build plan.

## Docs

- `docs/Doc1_Technical_Architecture.md`: architecture, data flow, ML config, decision policy
- `docs/Doc2_GitHub_Monorepo_Structure.md`: the folder layout this repo follows
- `docs/Doc3_Execution_Guide.md`: chronological build phases
- `docs/Component_2_Dynamic_Model_Updating.md`: research positioning and design of CADAL
- `docs/adr/`: decision records (detector choice, attribute before acting, early stop, restarts)
