# Document 1: Technical Architecture
## Self-Healing AI-Driven Failure Prediction & Recovery Framework

---

## 1. System Overview

This framework creates a closed-loop, autonomous reliability system for Kubernetes-hosted microservices. It continuously ingests operational telemetry, predicts imminent failures using online streaming ML, triggers graduated remediation actions through a policy-aware decision engine, and surfaces all activity to operators via a real-time React dashboard.

**Core Design Principles**
- **Online Learning First**: No batch retraining cycles. The river ML library processes every Prometheus scrape as a stream event, updating model weights in microseconds.
- **Language-Native Strengths**: Python (FastAPI) owns ML inference; C# (.NET) owns stateful orchestration and policy enforcement; React owns observability UX.
- **Kubernetes-Native Recovery**: All remediation actions are expressed as Kubernetes API calls — no bespoke restart scripts or SSH agents.
- **YARP as the Intelligent Proxy**: YARP (Yet Another Reverse Proxy) sits at the ingress layer and is the execution point for traffic-shifting recovery actions, controlled programmatically by the .NET Decision Engine.

---

## 2. Component Inventory

| Component | Technology | Responsibility |
|---|---|---|
| Metrics Collector | Prometheus + node-exporter + kube-state-metrics | Scrapes CPU, memory, latency, error rate, saturation from all pods |
| Telemetry Ingestion API | FastAPI (Python 3.11) | Receives **JSON** metric payloads via HTTP; normalises into feature vectors |
| Streaming ML Engine | river (Half-Space Trees) + ADWIN | Online anomaly detection; concept drift detection; anomaly scoring |
| Model Registry | MLflow (self-hosted) | Tracks experiment runs, model versions, metric snapshots; triggers rollback |
| Decision Engine | .NET 8 Worker Service | Consumes ML scores; reads `selfheal.io/upstreams` K8s annotations to build DAG; dispatches actions |
| Execution Layer | YARP Reverse Proxy + Kubernetes API | Executes traffic rerouting, scale events, pod restarts, circuit breaks |
| Event Bus | Redis Streams + Redis Pub/Sub | Streams for ML→Decision Engine; Pub/Sub for fan-out to all WebSocket replicas |
| Primary Datastore | **TimescaleDB + pgvector** (PostgreSQL) | Time-series metric retention + vector index for LLM/RAG — replaces Prometheus TSDB for app queries |
| Observability Dashboard | React 18 + Vite + Tailwind CSS | Displays live service health, anomaly scores, active incidents, copilot chat |
| LLM Copilot / RCA Engine | LangChain + **pgvector** (TimescaleDB) | RAG over telemetry stored in pgvector; auto-generates post-mortems; NL query interface |
| Chaos Injection | Chaos Mesh (Kubernetes operator) | Introduces controlled faults for system validation and HST stress testing |

---

## 3. End-to-End Data Flow

### 3.1 Telemetry Ingestion Path

> **Correction applied:** Prometheus `remote_write` with Snappy/Protobuf is removed to avoid
> C-compilation issues in multi-stage Docker builds. Instead, a lightweight Prometheus
> `webhook_config` (or a sidecar PromQL poller) forwards metrics as standard JSON.

```
[Kubernetes Pods]
        │  (expose /metrics endpoint)
        ▼
[Prometheus Server]  ─── scrape interval: 15s ───►  time-series database (TSDB)
        │
        │  Option A: alertmanager webhook_config → JSON POST
        │  Option B: sidecar PromQL poller (queries /api/v1/query_range, posts JSON)
        ▼
[FastAPI Ingestion Service]  POST /ingest/metrics  (Content-Type: application/json)
        │   Body: { "service_id": "svc-a", "timestamp": 1719000000.0,
        │           "metrics": { "cpu_rate": 0.72, "memory_bytes": 1.2e9, ... } }
        │
        │  Feature Extraction:
        │    - sliding window (60s) per service
        │    - z-score normalisation per feature
        │    - derived signals: error_rate_delta, latency_p99_trend
        ▼
[Feature Vector Store]  (in-memory ring buffer, Redis-backed)
        │
        ├──► [river HST Model]  ──► anomaly_score (0.0–1.0)
        │         │
        │         ▼
        │    [ADWIN Detector]  ──► drift_detected: bool
        │         │
        │         ├──► [MLflow Client]  ──► log metric + trigger rollback if drift
        │         │
        │         └──► [TimescaleDB]   ──► INSERT INTO metric_events (hypertable)
        │
        └──► [Redis Streams]   ──► stream: "anomaly_events"
             [Redis Pub/Sub]   ──► channel: "ws:anomaly_broadcast"
                    key: {service_id, score, timestamp, drift_flag}
```

**Key metrics collected per service:**
- `container_cpu_usage_seconds_total` (rate over 2m)
- `container_memory_working_set_bytes`
- `http_request_duration_seconds` (P50, P95, P99)
- `http_requests_total` (rate, split by status code)
- `container_network_receive_bytes_total` / `transmit_bytes_total`
- `kube_pod_status_ready` / `kube_pod_container_status_restarts_total`

### 3.2 Decision & Execution Path

```
[Redis Streams]  "anomaly_events"
        │
        ▼
[.NET Decision Engine]  (Worker Service with BackgroundService loop)
        │
        │  Step 1 — Threshold Classification:
        │    score < 0.5  → WATCH (log only)
        │    score 0.5–0.7 → WARN  (alert + pre-warm replica)
        │    score 0.7–0.85 → DEGRADE (circuit break + scale +1)
        │    score > 0.85  → CRITICAL (reroute + restart + rollback)
        │
        │  Step 2 — Dependency Graph Traversal:
        │    Kubernetes API → list Deployments in selfheal-apps namespace
        │    Read annotation selfheal.io/upstreams (comma-separated service IDs)
        │    Build in-memory DAG; refresh every 60s via HealthCheckWorker
        │    Propagate WARN status to all dependents of failing service
        │
        │  Step 3 — Action Dispatch:
        ├──► [YARP Admin API]  → traffic weight update (0% to failing pod)
        ├──► [Kubernetes API]  → scale Deployment / delete Pod / rollout undo
        ├──► [Redis Streams]   → publish "action_receipt" event
        └──► [MLflow REST API] → tag experiment run with remediation context
```

### 3.3 Real-Time Dashboard Streaming Path

> **Correction applied:** The in-memory `active_connections` set is removed. Because the
> FastAPI backend runs across multiple replicas under HPA, a single replica cannot know
> about WebSocket clients connected to other replicas. Redis Pub/Sub solves this: any pod
> that scores an anomaly publishes to channel `ws:anomaly_broadcast`; **every** FastAPI
> replica subscribes to that channel and pushes the message to its own locally-connected
> WebSocket clients.

```
[Any FastAPI replica]  ── scores anomaly ──►  Redis Pub/Sub PUBLISH ws:anomaly_broadcast
                                                          │
                     ┌────────────────────────────────────┤
                     │                                    │
        [FastAPI Pod 1]                       [FastAPI Pod 2]   … [Pod N]
        SUBSCRIBE ws:anomaly_broadcast        SUBSCRIBE ws:anomaly_broadcast
        → push to Pod-1 WS clients           → push to Pod-2 WS clients
        │
        ▼
[FastAPI WebSocket Gateway]  ws://gateway/ws/events
        │
        │  Multiplexes (via Redis Pub/Sub listener per pod):
        │    - anomaly_score updates (per service, driven by ingest cadence)
        │    - active_incidents list
        │    - action_receipts (what the engine just did)
        │    - drift_alerts
        │    - llm_rca_summaries
        │
        ▼
[React Dashboard]  useWebSocket() hook (native WebSocket API)
        │
        ├──► ServiceHealthGrid  (live status tiles with score sparklines)
        ├──► AnomalyScoreChart  (Recharts time-series, rolling 10-min window)
        ├──► IncidentFeed       (real-time action log with severity badges)
        ├──► DependencyGraph    (D3.js force-directed service map, edges pulse red)
        └──► CopilotChatPanel   (NL queries → LangChain RAG → streaming response)
```

---

## 4. Half-Space Trees — Algorithm Role & Configuration

Half-Space Trees (HST) are the primary anomaly detector because:

1. **O(1) amortized update cost** — each new metric scrape updates the model in constant time, critical at Prometheus 15s scrape intervals across 28+ services.
2. **No distribution assumption** — works on multivariate telemetry without assuming Gaussian distributions (memory and network I/O are highly skewed).
3. **Native river integration** — `river.anomaly.HalfSpaceTrees` is production-ready and fits the `learn_one / score_one` streaming API.

**Configuration per service instance:**
```python
from river.anomaly import HalfSpaceTrees

hst = HalfSpaceTrees(
    n_trees=25,          # ensemble size — accuracy vs. speed trade-off
    height=15,           # tree depth — larger = finer-grained partitions
    window_size=250,     # reference window (≈ 250 × 15s ≈ 62.5 min of history)
    seed=42
)
```

**ADWIN Drift Detection:**
```python
from river.drift import ADWIN

adwin = ADWIN(delta=0.002)  # false-positive rate 0.2%
# Triggers when anomaly_score distribution shifts — signals concept drift
# (e.g., a new deployment changes baseline behaviour)
# On trigger → MLflow rolls back to last stable model checkpoint
```

---

## 5. .NET Decision Engine — Dependency-Aware Policy

> **Correction applied:** Consul is entirely removed. The dependency graph is built purely
> from the Kubernetes API by reading the annotation `selfheal.io/upstreams` on each
> Deployment in the `selfheal-apps` namespace. No external service registry is required.

The Decision Engine is a `BackgroundService` that maintains an in-memory dependency graph built dynamically from the Kubernetes API. The graph is a directed acyclic graph (DAG) where edges represent "service A calls service B", encoded as Kubernetes Deployment annotations.

**Annotation format (applied to each target Deployment):**
```yaml
metadata:
  annotations:
    selfheal.io/upstreams: "svc-auth,svc-inventory"   # services THIS deployment calls
    selfheal.io/deployment-name: "service-b-orders"
```

**Graph construction (runs at startup + every 60 seconds):**
```csharp
// List all Deployments in selfheal-apps namespace
var deployments = await _k8s.ListNamespacedDeploymentAsync("selfheal-apps");
foreach (var dep in deployments.Items) {
    var upstreams = dep.Metadata.Annotations
        .GetValueOrDefault("selfheal.io/upstreams", "")
        .Split(',', StringSplitOptions.RemoveEmptyEntries);
    _graph.AddNode(dep.Metadata.Name, upstreams);
}
```

**Cascading logic:**
```
If Service B (anomaly_score > 0.85):
  → CRITICAL action on B
  → Traverse reverse edges → find all services A where A→B
  → For each upstream A: elevate status to WARN if A.score > 0.3
  → For each downstream C where B→C: pre-emptively scale C by +1 replica
```

**YARP integration for traffic control:**

YARP exposes a runtime configuration API (`IReverseProxyStatefulRouter`). The Decision Engine patches cluster weights directly:
```csharp
// Set failing pod's weight to 0 — zero traffic, no kill
_proxyConfig.UpdateClusterDestinationWeight(
    clusterId: serviceId,
    destinationId: failingPodIP,
    weight: 0
);
```
This achieves graceful traffic drain without pod termination, allowing in-flight requests to complete.

---

## 6. MLflow Model Registry Integration

| Event | MLflow Action |
|---|---|
| HST model initialised | `mlflow.start_run()` — log hyperparameters |
| Every 500 stream events | Log rolling `mean_anomaly_score`, `drift_count` as metrics |
| ADWIN drift detected | Log drift event; promote current run as "CANDIDATE"; load last "PRODUCTION" model |
| Rollback completed | Tag new run as "PRODUCTION"; archive drifted run |
| Chaos test completed | Log chaos test results as a child run under parent experiment |

**Model versioning strategy:** Each service has its own MLflow experiment (`experiment_name = f"hst_{service_id}"`). Models are serialised using `pickle` within the run artefacts and loaded by the FastAPI service on rollback.

---

## 7. Security Architecture

| Concern | Implementation |
|---|---|
| Inter-service auth | mTLS via Istio or cert-manager-issued certificates |
| Redis access | AUTH password + TLS; Redis Streams ACL per consumer group |
| Kubernetes API access | Dedicated ServiceAccount with minimal RBAC (`get/patch Deployments`, `delete Pods`) |
| MLflow artifact store | S3-compatible (MinIO in-cluster) with IAM-style bucket policies |
| TimescaleDB access | `postgresql://` connection string in Kubernetes Secret; `pgvector` extension enabled at init |
| YARP admin API | Localhost-only binding; Decision Engine co-deployed in same pod |
| React dashboard | JWT auth via Auth0 / Keycloak; WebSocket connections carry bearer token |
| LLM API keys | Kubernetes Secrets → mounted as environment variables (never in image) |

---

## 8. Deployment Topology (Kubernetes Namespaces)

```
cluster
├── namespace: monitoring
│     ├── prometheus            (StatefulSet, PVC for TSDB)
│     ├── grafana               (Deployment)
│     └── alertmanager          (Deployment)
│
├── namespace: selfheal-system
│     ├── fastapi-ml-backend    (Deployment, 2 replicas)
│     ├── dotnet-decision-engine (Deployment, 2 replicas)
│     ├── yarp-gateway          (Deployment, 3 replicas, LoadBalancer Service)
│     ├── redis                 (StatefulSet, PVC — Streams + Pub/Sub)
│     ├── timescaledb           (StatefulSet, PVC — pgvector extension enabled)
│     └── mlflow-server         (Deployment + MinIO StatefulSet)
│
├── namespace: selfheal-apps
│     ├── service-a through service-n   (target microservices)
│     └── chaos-mesh-operator           (DaemonSet)
│
└── namespace: selfheal-frontend
      └── react-dashboard        (Deployment + Ingress)
```

---

## 9. Dataset Selection — Recommendation

### Comparison Matrix

| Dataset | Streaming Native | Multivariate | Ground Truth | Microservice Context | Size | Verdict |
|---|---|---|---|---|---|---|
| **NAB** | ✅ Designed for it | ❌ Univariate per file | ✅ Labelled windows | ⚠️ Generic IT ops | Small | Best for algorithm benchmarking |
| **SMD** | ✅ Can be streamed | ✅ 38 features/machine | ✅ Per-timestamp labels | ✅ Server telemetry | Medium | Best for feature-rich training |
| **Multi-Source** | ⚠️ Batch | ✅ Metrics+Logs+Traces | ✅ Injected faults | ✅ Best fit | Large | Good for multi-modal future work |
| **Alibaba Trace** | ⚠️ Batch | ✅ Rich traces | ❌ No labels | ✅ Cloud-native | Very Large | Overkill; label work needed |

### ✅ Recommendation: SMD as Primary + NAB as Benchmark

**Primary training dataset: Server Machine Dataset (SMD)**
- 38 features per entity (CPU, memory, network — identical to what Prometheus collects)
- 28 machine entities = 28 independent HST model training scenarios
- Ground-truth anomaly labels for precision/recall scoring against HST scores
- Streams naturally: load entity CSV row-by-row → feed to `hst.learn_one()` / `hst.score_one()`

**Benchmark/evaluation harness: NAB**
- Use NAB's `standard_profile` scorer to compute NAB score against HST predictions
- Purpose-built for streaming detectors — gives you a defensible, published benchmark number
- 58 real-world time series covering server metrics, cloud ops, and network traffic

**Acquisition:**
```bash
# SMD
git clone https://github.com/NetManAIOps/OmniAnomaly
# Dataset at: OmniAnomaly/ServerMachineDataset/

# NAB
git clone https://github.com/numenta/NAB
# Data at: NAB/data/
```

**Rationale for rejecting Multi-Source and Alibaba as primary:**
- Multi-Source requires significant preprocessing to align metrics/logs/traces timelines
- Alibaba lacks anomaly labels, requiring unsupervised evaluation only
- Both are better suited for Phase 2 research after core HST pipeline is validated on SMD+NAB
