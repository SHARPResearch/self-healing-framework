# Document 3: Step-by-Step Execution Guide
## Chronological Development Phases

> **Convention:** Each phase lists **Manual Tasks** (environment, tooling, config) before **Coding Tasks** (files to write). Phases are sequential; do not start Phase N+1 until Phase N's verification step passes.

---

## Phase 0: Workstation Prerequisites

### Manual Tasks

1. **Install core tooling:**
   ```bash
   # Python 3.11+
   pyenv install 3.11.9 && pyenv global 3.11.9

   # .NET 8 SDK
   # Download from https://dotnet.microsoft.com/download/dotnet/8.0

   # Node.js 20 LTS + pnpm
   nvm install 20 && npm install -g pnpm

   # Docker Desktop (enable Kubernetes in settings OR use Minikube)
   # Download from https://www.docker.com/products/docker-desktop

   # Minikube
   brew install minikube   # macOS
   # Windows: choco install minikube

   # kubectl
   brew install kubectl

   # Helm 3
   brew install helm

   # uv (fast Python package manager)
   pip install uv

   # pre-commit
   pip install pre-commit
   ```

2. **Configure Minikube with required resources:**
   ```bash
   minikube start \
     --cpus=6 \
     --memory=10240 \
     --disk-size=50g \
     --kubernetes-version=v1.29.0 \
     --addons=ingress,metrics-server,storage-provisioner

   # Verify
   kubectl get nodes
   minikube status
   ```

3. **Install Chaos Mesh:**
   ```bash
   helm repo add chaos-mesh https://charts.chaos-mesh.org
   helm repo update
   kubectl create namespace chaos-testing
   helm install chaos-mesh chaos-mesh/chaos-mesh \
     --namespace=chaos-testing \
     --version 2.6.2 \
     --set chaosDaemon.runtime=containerd \
     --set chaosDaemon.socketPath=/run/containerd/containerd.sock
   # Verify
   kubectl get pods -n chaos-testing
   ```

4. **Install kube-prometheus-stack (Prometheus + Grafana):**
   ```bash
   helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
   helm repo update
   kubectl create namespace monitoring
   helm install kube-prometheus prometheus-community/kube-prometheus-stack \
     --namespace monitoring \
     --set grafana.adminPassword=admin \
     --set prometheus.prometheusSpec.scrapeInterval=15s
   # Verify
   kubectl get pods -n monitoring
   ```

5. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_ORG/self-healing-framework.git
   cd self-healing-framework
   pre-commit install
   ```

### Coding Tasks
- Write `scripts/start-minikube.sh` (wraps Minikube start command with correct flags)
- Write `Makefile` with targets: `dev`, `test-ml`, `test-dotnet`, `test-fe`, `deploy-stg`
- Write `docker-compose.yml` (Redis + MLflow + all services for local dev)

**Phase 0 Verification:**
```bash
kubectl cluster-info
helm list -A  # should show chaos-mesh, kube-prometheus
```

---

## Phase 1: Monorepo Scaffolding

### Manual Tasks

1. **Create namespace structure:**
   ```bash
   kubectl apply -f infrastructure/kubernetes/namespaces.yaml
   ```

2. **Set up MLflow locally for development:**
   ```bash
   pip install mlflow[extras]
   mlflow server \
     --backend-store-uri sqlite:///mlflow.db \
     --default-artifact-root ./mlflow-artifacts \
     --host 0.0.0.0 \
     --port 5001 &
   # UI: http://localhost:5001
   ```

3. **Start Redis locally:**
   ```bash
   docker run -d --name redis-dev \
     -p 6379:6379 \
     redis:7-alpine \
     redis-server --appendonly yes
   ```

4. **Start TimescaleDB with pgvector locally** *(replaces standalone FAISS / Prometheus TSDB for app queries)*:
   ```bash
   docker run -d --name timescaledb-dev \
     -e POSTGRES_PASSWORD=selfheal \
     -e POSTGRES_DB=selfheal \
     -p 5432:5432 \
     timescale/timescaledb-ha:pg16
   # Wait ~10s then initialise schema:
   docker exec timescaledb-dev psql -U postgres -d selfheal -c "
     CREATE EXTENSION IF NOT EXISTS timescaledb;
     CREATE EXTENSION IF NOT EXISTS vector;
     CREATE TABLE IF NOT EXISTS metric_events (
       time            TIMESTAMPTZ NOT NULL,
       service_id      TEXT NOT NULL,
       anomaly_score   DOUBLE PRECISION,
       severity        TEXT,
       drift_detected  BOOLEAN,
       features        JSONB
     );
     SELECT create_hypertable('metric_events','time', if_not_exists => TRUE);
     CREATE TABLE IF NOT EXISTS telemetry_embeddings (
       id          BIGSERIAL PRIMARY KEY,
       service_id  TEXT,
       created_at  TIMESTAMPTZ DEFAULT NOW(),
       content     TEXT,
       embedding   vector(384)
     );
     CREATE INDEX ON telemetry_embeddings
       USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
   "
   ```

### Coding Tasks

1. **Write `infrastructure/kubernetes/namespaces.yaml`:**
   ```yaml
   # Three namespaces: selfheal-system, selfheal-apps, selfheal-frontend
   ```

2. **Initialise Python `ml-backend` service:**
   ```bash
   cd services/ml-backend
   uv init --python 3.11
   uv add fastapi uvicorn[standard] redis river mlflow pydantic-settings prometheus-client \
          asyncpg pgvector sqlalchemy[asyncio]
   uv add --dev pytest pytest-asyncio httpx
   # NOTE: Do NOT add python-snappy or prometheus-remote-storage
   ```

3. **Write `services/ml-backend/app/main.py`** — FastAPI app factory with lifespan context manager that initialises Redis connection and HST model registry on startup.

4. **Write `services/ml-backend/app/config.py`** — Pydantic `Settings` class reading `REDIS_URL`, `MLFLOW_TRACKING_URI`, `PROMETHEUS_URL` from environment.

5. **Initialise .NET Decision Engine:**
   ```bash
   cd services/decision-engine
   dotnet new worker -n DecisionEngine
   dotnet add package StackExchange.Redis
   dotnet add package KubernetesClient
   dotnet add package Yarp.ReverseProxy
   dotnet add package Microsoft.Extensions.Http
   ```

6. **Initialise YARP Gateway:**
   ```bash
   cd services/yarp-gateway
   dotnet new web -n YarpGateway
   dotnet add package Yarp.ReverseProxy
   ```

7. **Initialise React frontend:**
   ```bash
   cd frontend
   pnpm create vite . --template react-ts
   pnpm add tailwindcss @tailwindcss/vite recharts d3 zustand axios
   pnpm add -D @types/d3 vitest @testing-library/react playwright
   pnpm dlx tailwindcss init -p
   ```

**Phase 1 Verification:**
```bash
cd services/ml-backend && uvicorn app.main:app --reload  # GET /health → 200
cd services/decision-engine && dotnet build              # 0 errors
cd frontend && pnpm dev                                  # Vite server at :5173
```

---

## Phase 2: Dataset Acquisition & HST Warm-Up Training

### Manual Tasks

1. **Download SMD dataset:**
   ```bash
   git clone https://github.com/NetManAIOps/OmniAnomaly.git /tmp/omnianomaly
   cp -r /tmp/omnianomaly/ServerMachineDataset datasets/smd/raw/
   ```

2. **Download NAB dataset:**
   ```bash
   git clone https://github.com/numenta/NAB.git /tmp/nab
   cp -r /tmp/nab/data datasets/nab/raw/
   cp -r /tmp/nab/labels datasets/nab/raw/
   ```

3. **Launch Jupyter for notebook exploration:**
   ```bash
   pip install jupyter
   jupyter lab ml-pipeline/notebooks/
   ```

### Coding Tasks

1. **Write `datasets/smd/preprocess.py`:**
   - Load SMD CSVs (`machine-1-1.txt` through `machine-3-11.txt`)
   - Standardise column names to canonical feature schema: `cpu_rate`, `memory_used`, `network_rx`, `network_tx`, `disk_io_read`, `disk_io_write`
   - Output: `datasets/smd/processed/{entity_id}.parquet`

2. **Write `ml-pipeline/notebooks/01_smd_exploration.ipynb`:**
   - Load SMD entity, visualise time series
   - Feed row-by-row to `HalfSpaceTrees`, plot anomaly score
   - Compare score peaks to ground-truth labels

3. **Write `ml-pipeline/scripts/warm_up_hst.py`:**
   ```python
   # Streams all SMD training split rows through HST
   # Logs to MLflow: n_trees, height, window_size, final NAB score
   # Serialises trained model to MLflow artifact store
   # Marks run as "PRODUCTION" in MLflow Model Registry
   ```

4. **Write `ml-pipeline/notebooks/02_nab_benchmarking.ipynb`:**
   - Run warm-up trained HST on NAB `realKnownCause/` files
   - Compute NAB score using NAB's `scoreHelper.py`
   - Compare vs. Isolation Forest baseline

5. **Write `ml-pipeline/scripts/run_nab_benchmark.py`** — CLI version of notebook for CI pipeline.

**Phase 2 Verification:**
```bash
python ml-pipeline/scripts/warm_up_hst.py --entity machine-1-1
# Expected output: MLflow run logged, model registered, NAB score > 0.55
```

---

## Phase 3: FastAPI ML Backend — Full Implementation

### Manual Tasks

1. **Set environment variables:**
   ```bash
   cp services/ml-backend/.env.example services/ml-backend/.env
   # Edit .env:
   # REDIS_URL=redis://localhost:6379
   # MLFLOW_TRACKING_URI=http://localhost:5001
   # PROMETHEUS_URL=http://localhost:9090
   # HST_N_TREES=25
   # HST_HEIGHT=15
   # HST_WINDOW_SIZE=250
   ```

2. **Configure Prometheus remote_write to push to FastAPI** (add to `kube-prometheus` values):
   ```yaml
   prometheus:
     prometheusSpec:
       remoteWrite:
         - url: http://ml-backend.selfheal-system.svc/ingest/prometheus
   ```

### Coding Tasks

1. **Write `app/core/feature_extractor.py`:**
   - Accepts raw Prometheus `remote_write` protobuf OR PromQL JSON response
   - Extracts: `cpu_rate_2m`, `mem_bytes`, `latency_p99`, `error_rate`, `net_rx`, `net_tx`, `restart_count`
   - Returns: `FeatureVector(service_id, timestamp, features: dict[str, float])`

2. **Write `app/core/ring_buffer.py`:**
   - `RingBuffer(maxlen=500)` per service
   - Thread-safe via `asyncio.Lock`
   - `append(vector)` / `get_window(n)` methods

3. **Write `app/ml/hst_model.py`:**
   ```python
   class HSTModelRegistry:
       """Per-service Half-Space Trees instances."""
       def __init__(self, n_trees, height, window_size):
           self._models: dict[str, HalfSpaceTrees] = {}
           self._lock = asyncio.Lock()

       async def score(self, service_id: str, features: dict) -> float:
           async with self._lock:
               if service_id not in self._models:
                   self._models[service_id] = HalfSpaceTrees(...)
               model = self._models[service_id]
               score = model.score_one(features)
               model.learn_one(features)
               return score
   ```

4. **Write `app/ml/adwin_detector.py`:**
   - Wraps `river.drift.ADWIN(delta=0.002)`
   - `update(score)` → returns `(drift_detected: bool, change_point: float | None)`
   - On drift: triggers `model_manager.rollback(service_id)`

5. **Write `app/ml/model_manager.py`:**
   - `log_metrics(service_id, step, score, drift_count)` → `mlflow.log_metrics()`
   - `rollback(service_id)` → loads last "PRODUCTION" model from MLflow artifact store, replaces in `HSTModelRegistry`
   - `promote(service_id, run_id)` → transitions model to "PRODUCTION" stage

6. **Write `app/api/routes/ingest.py`:**
   - `POST /ingest/metrics` — accepts `MetricPayload`, runs feature extraction, scores with HST, publishes to Redis Streams

7. **Write `app/api/websocket.py`:**
   - `GET /ws/events` — WebSocket endpoint
   - Spawns `asyncio.Task` that `XREAD`s Redis Streams ("anomaly_events", "action_receipts")
   - Serialises events as JSON and sends over WebSocket
   - Handles client disconnect gracefully

8. **Write unit tests** for `hst_model.py`, `adwin_detector.py`, `feature_extractor.py`

**Phase 3 Verification:**
```bash
cd services/ml-backend
pytest tests/ -v                           # All tests pass
uvicorn app.main:app --reload
curl -X POST localhost:8000/ingest/metrics \
  -H "Content-Type: application/json" \
  -d '{"service_id":"svc-a","metrics":{...}}'
# Response: {"anomaly_score": 0.23, "drift_detected": false}
```

---

## Phase 4: .NET Decision Engine

### Manual Tasks

1. **Configure Kubernetes RBAC for Decision Engine:**
   ```bash
   kubectl apply -f infrastructure/kubernetes/rbac/decision-engine-sa.yaml
   kubectl apply -f infrastructure/kubernetes/rbac/cluster-role-binding.yaml
   ```
   The ServiceAccount needs: `get`, `patch` on `Deployments`; `delete` on `Pods`; `create` on `Events`.

2. **Annotate target Deployments with dependency metadata** *(no Consul — K8s annotations are the source of truth)*:
   ```bash
   kubectl annotate deployment service-b-orders \
     selfheal.io/upstreams="service-a-auth,service-c-inventory" -n selfheal-apps
   kubectl annotate deployment service-c-inventory \
     selfheal.io/upstreams="service-a-auth" -n selfheal-apps
   kubectl annotate deployment service-d-notification \
     selfheal.io/upstreams="service-b-orders" -n selfheal-apps
   ```

### Coding Tasks

1. **Write `Engine/DependencyGraph.cs`:**
   - `Node { ServiceId, Namespace, DeploymentName, Upstreams, Downstreams }` using adjacency list
   - `RefreshFromKubernetesAsync(IKubernetes k8s, string ns)` — lists all Deployments in `selfheal-apps`, reads annotation `selfheal.io/upstreams`, rebuilds DAG; called every 60s
   - `GetAffectedServices(serviceId)` — BFS both directions, returns cascaded set

2. **Write `Engine/PolicyEvaluator.cs`:**
   ```csharp
   public RemediationLevel Evaluate(double anomalyScore) => anomalyScore switch {
       < 0.5  => RemediationLevel.Watch,
       < 0.7  => RemediationLevel.Warn,
       < 0.85 => RemediationLevel.Degrade,
       _      => RemediationLevel.Critical
   };
   ```

3. **Write `Engine/ActionDispatcher.cs`:**
   - Receives `(AnomalyEvent, RemediationLevel, IEnumerable<ServiceNode> cascaded)`
   - Selects and invokes the appropriate `IActionExecutor`
   - Publishes `ActionReceipt` to Redis Streams "action_receipts"

4. **Write `Executors/YarpTrafficShifter.cs`:**
   - `HttpClient` calling YARP's internal `AdminController`
   - `ShiftTraffic(serviceId, failingPodIP, weightPercent)` → `PATCH /admin/cluster`

5. **Write `Executors/KubernetesExecutor.cs`:**
   - Uses `KubernetesClient` NuGet package
   - `ScaleDeployment(namespace, name, replicas)`
   - `DeletePod(namespace, podName)`
   - `RollbackDeployment(namespace, name)` → `AppsV1Api.CreateNamespacedDeploymentRollback`

6. **Write `Workers/AnomalyConsumerWorker.cs`:**
   - Inherits `BackgroundService`
   - Infinite loop: `XREADGROUP` from Redis Streams "anomaly_events" consumer group "decision-engine"
   - Deserialises `AnomalyEvent` → `PolicyEvaluator.Evaluate()` → `ActionDispatcher.Dispatch()`
   - `XACK` after successful dispatch

7. **Write integration test** that sends mock `AnomalyEvent` via Redis and verifies `ActionReceipt` published.

**Phase 4 Verification:**
```bash
cd services/decision-engine && dotnet test   # All tests green
dotnet run                                   # Worker starts, connects to Redis
# Send test event:
python scripts/seed-demo-data.py --score 0.92 --service svc-d
# Observe logs: "CRITICAL action dispatched for svc-d"
```

---

## Phase 5: YARP Gateway

### Manual Tasks

1. **Plan service routing table** — document which backend services each YARP route points to, including health-check paths.

### Coding Tasks

1. **Write `appsettings.json`** — initial YARP static config:
   ```json
   {
     "ReverseProxy": {
       "Routes": { "route-svc-a": {"ClusterId": "cluster-svc-a", "Match": {"Path": "/api/auth/{**catch-all}"}} },
       "Clusters": { "cluster-svc-a": {"Destinations": {"pod-1": {"Address": "http://service-a:8080"}}} }
     }
   }
   ```

2. **Write `Configuration/DynamicRouteProvider.cs`:**
   - Implements `IProxyConfigProvider`
   - Holds `InMemoryProxyConfig` (thread-safe)
   - `PatchWeight(clusterId, destinationId, weight)` — called by `AdminController`

3. **Write `Controllers/AdminController.cs`:**
   - `PATCH /admin/cluster` — receives `{clusterId, destinationId, weight}`, calls `DynamicRouteProvider.PatchWeight()`
   - Bound to `localhost` only via `UseWhen` middleware filter

**Phase 5 Verification:**
```bash
cd services/yarp-gateway && dotnet run
curl http://localhost:5000/api/auth/health  # Proxied to service-a
curl -X PATCH http://localhost:5000/admin/cluster \
  -d '{"clusterId":"cluster-svc-a","destinationId":"pod-1","weight":0}'
# Subsequent requests to /api/auth → 503 (no healthy destinations)
```

---

## Phase 6: React Frontend Dashboard

### Manual Tasks

1. **Design WebSocket message contract** — agree JSON schemas for `anomaly_score`, `action_receipt`, `drift_alert` messages with the FastAPI team (yourself).

2. **Install Recharts and D3 types:**
   ```bash
   cd frontend && pnpm add recharts @types/recharts
   ```

### Coding Tasks

1. **Write `src/hooks/useWebSocket.ts`:**
   - Native `WebSocket` with exponential backoff reconnect
   - Returns `{ lastMessage, connectionStatus }`

2. **Write `src/hooks/useAnomalyStream.ts`:**
   - Wraps `useWebSocket`, parses JSON, dispatches to Zustand stores

3. **Write `src/stores/servicesStore.ts`:**
   ```typescript
   interface ServiceState {
     serviceId: string;
     anomalyScore: number;
     status: 'healthy' | 'degraded' | 'critical';
     scoreHistory: { ts: number; score: number }[];
   }
   ```

4. **Write `src/components/dashboard/ServiceHealthGrid.tsx`:**
   - Grid of `ServiceTile` cards — colour coded by status
   - Each tile shows current score, trend sparkline, last action

5. **Write `src/components/dashboard/AnomalyScoreChart.tsx`:**
   - Recharts `LineChart` with `ReferenceLine` at 0.5 (warn) and 0.85 (critical)
   - Rolling 10-minute window, updates on every WebSocket message

6. **Write `src/components/dashboard/DependencyGraph.tsx`:**
   - D3.js `forceSimulation` — nodes are services, edges are dependencies
   - Failing service node turns red; edges from dependents pulse amber

7. **Write `src/components/copilot/CopilotChatPanel.tsx`:**
   - Textarea input + `fetch()` with `ReadableStream` for SSE streaming response
   - Renders markdown in chat bubbles (use `react-markdown`)

8. **Write E2E test** (Playwright): Launch dev stack → verify WebSocket connects → verify score chart renders on simulated anomaly event.

**Phase 6 Verification:**
```bash
cd frontend && pnpm dev
# Navigate to http://localhost:5173
# Open browser DevTools → Network → WS → verify messages streaming
pnpm test:e2e   # Playwright tests pass
```

---

## Phase 7: LLM Copilot Service

### Manual Tasks

1. **Set up LLM API access:**
   ```bash
   # Add to .env:
   OPENAI_API_KEY=sk-...   # or ANTHROPIC_API_KEY for Claude
   ```

2. **Install FAISS:**
   ```bash
   cd services/llm-copilot
   uv add langchain langchain-openai faiss-cpu sentence-transformers
   ```

### Coding Tasks

1. **Write `rag/indexer.py`:**
   - Subscribes to Redis Streams — indexes every anomaly event as a document
   - Embeds with `sentence-transformers/all-MiniLM-L6-v2`
   - Stores in FAISS index (persisted to disk every 1000 events)

2. **Write `rag/retriever.py`:**
   - `retrieve(query, top_k=5)` — FAISS similarity search over telemetry documents
   - Returns list of `TelemetryDocument(service_id, timestamp, anomaly_score, action_taken)`

3. **Write `chains/rca_chain.py`:**
   - LangChain `RetrievalQA` chain with system prompt:
     > "You are an SRE expert. Given the following telemetry events, identify the root cause and provide a concise technical explanation."

4. **Write `chains/postmortem_chain.py`:**
   - Triggered when incident is resolved (Decision Engine publishes "incident_resolved")
   - Generates structured post-mortem: Timeline, Root Cause, Impact, Remediation Steps, Prevention

5. **Write `api/chat.py`:**
   - `POST /chat` — streaming SSE response using `StreamingResponse`

**Phase 7 Verification:**
```bash
cd services/llm-copilot && uvicorn app.main:app --port 8001
curl -X POST localhost:8001/chat \
  -d '{"message":"Why is service-d failing?"}'
# Streams RCA response based on indexed telemetry
```

---

## Phase 8: Kubernetes Deployment & Integration Testing

### Manual Tasks

1. **Build and push all Docker images:**
   ```bash
   eval $(minikube docker-env)  # Use Minikube's Docker daemon
   docker build -t self-healing/ml-backend:dev services/ml-backend/
   docker build -t self-healing/decision-engine:dev services/decision-engine/
   docker build -t self-healing/yarp-gateway:dev services/yarp-gateway/
   docker build -t self-healing/frontend:dev frontend/
   ```

2. **Deploy via Helm:**
   ```bash
   helm upgrade --install self-healing-framework \
     ./infrastructure/helm/self-healing-framework \
     --namespace selfheal-system \
     --create-namespace \
     -f infrastructure/helm/self-healing-framework/values.yaml \
     --set mlBackend.image.tag=dev \
     --set decisionEngine.image.tag=dev
   ```

3. **Run Chaos Mesh experiment:**
   ```bash
   kubectl apply -f infrastructure/helm/self-healing-framework/templates/chaos-mesh/pod-kill.yaml
   # Observe: Decision Engine detects failure → YARP reroutes → pod rescheduled
   ```

### Coding Tasks

1. **Write Helm templates** for all services (see Doc2 template list)
2. **Write `infrastructure/kubernetes/rbac/` manifests**
3. **Write `scripts/run-chaos-experiment.sh`** — applies chaos, polls anomaly score API, logs recovery timeline to CSV
4. **Write `scripts/seed-demo-data.py`** — pushes synthetic anomaly events to Redis for dashboard demo without requiring live Prometheus

**Phase 8 Verification:**
```bash
kubectl get pods -n selfheal-system   # All Running
kubectl logs -n selfheal-system deployment/decision-engine -f
# Chaos experiment: service killed → within 30s → action_receipt logged → pod restarted
```

---

## Phase 9: CI/CD Pipeline & Production Hardening

### Manual Tasks

1. **Set GitHub Actions secrets:** `DOCKER_HUB_TOKEN`, `KUBECONFIG_STAGING`, `MLFLOW_TRACKING_URI`
2. **Configure ArgoCD** pointing to `infrastructure/helm/` directory
3. **Set resource limits** in Helm values (CPU: 500m, Memory: 512Mi per service)

### Coding Tasks

1. **Write `.github/workflows/ci-ml-backend.yml`** — ruff lint → pytest → docker build → push
2. **Write `.github/workflows/ci-dotnet-engine.yml`** — dotnet build → dotnet test → docker build → push
3. **Write `.github/workflows/ci-frontend.yml`** — pnpm lint → vitest → playwright → docker build → push
4. **Write `.github/workflows/cd-deploy-staging.yml`** — on main merge → ArgoCD sync
5. **Write HPA manifests** — scale `ml-backend` 2–6 replicas based on Redis queue depth metric
6. **Write Network Policies** — deny-all default, allow only expected cross-service traffic

**Phase 9 Verification:**
- Push a PR → GitHub Actions CI passes
- Merge to main → ArgoCD deploys automatically
- `kubectl get hpa -n selfheal-system` shows configured HPA
