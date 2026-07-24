# Document 4: Claude Code Agent Prompts — The Tutorial
## Sequential Copy-Paste Prompts for Claude Code CLI

> **How to use:** Open a terminal in the monorepo root. Run `claude` to start a session. Copy-paste each prompt in order. Wait for the agent to finish before pasting the next one.
>
> **Prompt numbering:** P-01 through P-24. Each prompt is self-contained and references the file paths from Doc2.

---

## SECTION A: Monorepo Initialisation

---

### P-01 — Project Bootstrap & Makefile

```
You are a senior DevOps engineer bootstrapping a Python + .NET + React monorepo called
"self-healing-framework". The project is a self-healing AI system for Kubernetes microservices.

Create the following files exactly as specified:

1. `.gitignore` — comprehensive ignore for Python (__pycache__, .venv, *.pyc, dist/),
   .NET (bin/, obj/, *.user), Node (node_modules/, dist/, .next/), and Docker (.env).
   Also ignore: mlflow-artifacts/, mlflow.db, datasets/*/raw/, *.parquet.

2. `.editorconfig` — 4-space indent for Python/C#, 2-space for TypeScript/JSON/YAML.
   UTF-8, LF line endings, trim trailing whitespace.

3. `Makefile` — with these targets:
   - `dev`: runs `docker-compose up --build`
   - `test-ml`: runs `cd services/ml-backend && uv run pytest tests/ -v`
   - `test-dotnet`: runs `cd services/decision-engine && dotnet test`
   - `test-fe`: runs `cd frontend && pnpm test`
   - `test-all`: runs all three above in sequence
   - `deploy-stg`: runs helm upgrade command (see Doc2 for full command)
   - `chaos-run`: runs `bash scripts/run-chaos-experiment.sh`
   - `port-forward`: runs `bash scripts/port-forward-all.sh`

4. `.env.example` — with all required env vars:
   REDIS_URL=redis://localhost:6379
   MLFLOW_TRACKING_URI=http://localhost:5001
   PROMETHEUS_URL=http://localhost:9090
   HST_N_TREES=25
   HST_HEIGHT=15
   HST_WINDOW_SIZE=250
   OPENAI_API_KEY=your-key-here
   DECISION_ENGINE_URL=http://localhost:5002
   YARP_ADMIN_URL=http://localhost:5000/admin

5. `scripts/port-forward-all.sh` — bash script that kubectl port-forwards:
   - Prometheus: 9090:9090 from namespace monitoring
   - Grafana: 3000:3000 from namespace monitoring
   - MLflow: 5001:5001 from namespace selfheal-system
   - Redis: 6379:6379 from namespace selfheal-system
   - ML Backend: 8000:8000 from namespace selfheal-system
   - Decision Engine: 5002:5002 from namespace selfheal-system
   Each in background (&). Print "All port-forwards started." at end.

6. `README.md` — project overview (3 paragraphs), quick-start section (5 commands),
   and a link table to each document in docs/.
```

---

### P-02 — Docker Compose for Local Development  ✦ CORRECTED

```
You are a senior DevOps engineer. Create `docker-compose.yml` and
`docker-compose.override.yml` for the self-healing-framework monorepo.

ARCHITECTURAL CONSTRAINTS (apply strictly):
- TimescaleDB with pgvector is the PRIMARY datastore for both time-series metrics
  AND vector embeddings. There is NO standalone FAISS or separate vector DB.
- Redis serves BOTH Redis Streams (ML→Decision Engine) AND Redis Pub/Sub
  (fan-out to multi-replica WebSocket pods). No separate pub/sub broker needed.
- Do NOT add python-snappy, prometheus-remote-storage, or any protobuf dependencies.
- Do NOT add Consul or any service registry container.

`docker-compose.yml` must define these services:

- `redis`: image redis:7-alpine, port 6379:6379, volume redis-data:/data,
  command: redis-server --appendonly yes, healthcheck: redis-cli ping

- `timescaledb`: image timescale/timescaledb-ha:pg16, port 5432:5432,
  environment: POSTGRES_PASSWORD=selfheal, POSTGRES_DB=selfheal,
  volume: timescaledb-data:/home/postgres/pgdata/data,
  healthcheck: pg_isready -U postgres,
  After first start, run init SQL (via entrypoint or initdb script):
    CREATE EXTENSION IF NOT EXISTS timescaledb;
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS metric_events (
      time TIMESTAMPTZ NOT NULL, service_id TEXT NOT NULL,
      anomaly_score DOUBLE PRECISION, severity TEXT,
      drift_detected BOOLEAN, features JSONB);
    SELECT create_hypertable('metric_events','time',if_not_exists=>TRUE);
    CREATE TABLE IF NOT EXISTS telemetry_embeddings (
      id BIGSERIAL PRIMARY KEY, service_id TEXT, created_at TIMESTAMPTZ DEFAULT NOW(),
      content TEXT, embedding vector(384));
    CREATE INDEX ON telemetry_embeddings USING ivfflat (embedding vector_l2_ops)
      WITH (lists=100);
  Place this SQL in infrastructure/db/init.sql and mount as
  /docker-entrypoint-initdb.d/init.sql so it runs automatically on first start.

- `mlflow`: image ghcr.io/mlflow/mlflow:latest, port 5001:5001,
  command: mlflow server --backend-store-uri sqlite:///mlflow.db
  --default-artifact-root /mlflow-artifacts --host 0.0.0.0 --port 5001,
  volumes: mlflow-artifacts-vol:/mlflow-artifacts

- `ml-backend`: build ./services/ml-backend, port 8000:8000,
  env_file: .env, depends_on: [redis, mlflow, timescaledb]

- `decision-engine`: build ./services/decision-engine, port 5002:5002,
  env_file: .env, depends_on: [redis, ml-backend]

- `yarp-gateway`: build ./services/yarp-gateway, port 5000:5000,
  env_file: .env, depends_on: [decision-engine]

- `frontend`: build ./frontend, port 5173:80, depends_on: [ml-backend]

- `llm-copilot`: build ./services/llm-copilot, port 8001:8001,
  env_file: .env, depends_on: [redis, timescaledb]

Define named volumes: redis-data, timescaledb-data, mlflow-artifacts-vol

`docker-compose.override.yml` must:
- Mount source code volumes for hot-reload on ml-backend and llm-copilot
- Set ENVIRONMENT=development on all services
- Override ml-backend command to: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Update `.env.example` to add:
  TIMESCALEDB_URL=postgresql+asyncpg://postgres:selfheal@localhost:5432/selfheal

Also create `infrastructure/db/init.sql` containing the full schema SQL above.

Also create `scripts/seed-demo-data.py` — Python script (no deps beyond redis and asyncpg)
that:
1. Publishes 10 synthetic anomaly events to Redis stream "anomaly_events" AND
   Redis Pub/Sub channel "ws:anomaly_broadcast" (PUBLISH command, same JSON payload)
2. Inserts corresponding rows into timescaledb metric_events table
Fields: service_id (cycle: svc-a…svc-e), anomaly_score (random 0.3–0.95),
timestamp (unix ms), drift_detected (False). Print each event. Pause 500ms between events.
```

---

## SECTION B: FastAPI ML Backend

---

### P-03 — FastAPI App Foundation

```
You are a Python backend engineer. Create the FastAPI application foundation for
`services/ml-backend/`. The app handles real-time ML inference for microservice anomaly detection.

Files to create:

1. `services/ml-backend/pyproject.toml` — uv project file, Python 3.11,
   dependencies: fastapi>=0.111, uvicorn[standard], redis>=5, river>=0.21,
   mlflow>=2.12, pydantic-settings>=2, prometheus-client, httpx, numpy,
   asyncpg>=0.29, pgvector>=0.3, sqlalchemy[asyncio]>=2.0
   DO NOT add python-snappy, prometheus-remote-storage, or any protobuf library.
   These cause C-compilation failures in multi-stage Docker builds.

2. `services/ml-backend/app/config.py` — Pydantic BaseSettings class named `Settings`:
   Fields: REDIS_URL (str), MLFLOW_TRACKING_URI (str), PROMETHEUS_URL (str),
   HST_N_TREES (int=25), HST_HEIGHT (int=15), HST_WINDOW_SIZE (int=250),
   ENVIRONMENT (str="development"), LOG_LEVEL (str="INFO")
   Use model_config = SettingsConfigDict(env_file=".env")
   Export a module-level `settings = Settings()` singleton.

3. `services/ml-backend/app/main.py` — FastAPI app with:
   - async lifespan context manager that on startup: creates Redis connection pool
     (stored as app.state.redis), initialises HSTModelRegistry (app.state.hst_registry),
     logs "ML Backend started" with settings summary
   - on shutdown: closes Redis connection
   - includes routers: ingest, predict, models, health (all from app.api.routes)
   - adds CORS middleware allowing all origins (for dev)
   - adds a /metrics endpoint returning Prometheus text format (prometheus_client)

4. `services/ml-backend/app/schemas/metrics.py` — Pydantic models:
   - `ServiceMetrics`: service_id (str), timestamp (float), cpu_rate (float),
     memory_bytes (float), latency_p99_ms (float), error_rate (float),
     network_rx_bytes (float), network_tx_bytes (float),
     restart_count (int, default 0)
   - `MetricPayload`: service_id (str), timestamp (float), metrics (dict[str, float])
   - `FeatureVector`: service_id (str), timestamp (float), features (dict[str, float])

5. `services/ml-backend/app/schemas/prediction.py` — Pydantic models:
   - `AnomalyScore`: service_id (str), timestamp (float), score (float, ge=0, le=1),
     severity (Literal["watch","warn","degrade","critical"]),
     drift_detected (bool, default False)
   - `DriftAlert`: service_id (str), timestamp (float), previous_score_mean (float),
     current_score_mean (float), change_point (float | None)

6. `services/ml-backend/app/schemas/events.py` — Pydantic models:
   - `AnomalyEvent`: service_id, timestamp, anomaly_score, drift_detected, severity
   - `ActionReceipt`: service_id, timestamp, action_type (str), executor (str),
     success (bool), details (str)

7. `services/ml-backend/app/api/routes/health.py` — two endpoints:
   GET /health → {"status":"ok","service":"ml-backend"}
   GET /ready → checks Redis ping and returns 200 if ok, 503 if not

Write clean, type-annotated Python. Use `Annotated` for dependency injection.
```

---

### P-04 — Feature Extraction & Ring Buffer

```
You are a senior ML engineer. Implement the data pipeline utilities for
`services/ml-backend/app/core/`.

1. `app/core/feature_extractor.py`:
   Create class `FeatureExtractor` with method:
   `extract(payload: MetricPayload) -> FeatureVector`

   The method must:
   - Validate all required metric keys exist (raise ValueError with descriptive msg if not)
   - Compute derived features:
     * `error_rate_per_second` = metrics["http_errors"] / max(metrics["http_requests"], 1)
     * `memory_pressure` = metrics["memory_bytes"] / metrics.get("memory_limit_bytes", 2e9)
     * `latency_spike` = 1.0 if metrics["latency_p99_ms"] > 500 else 0.0
     * `restart_penalty` = min(metrics.get("restart_count", 0) / 5.0, 1.0)
   - Return FeatureVector with features dict containing:
     cpu_rate, memory_pressure, latency_p99_ms (normalised to 0-1 via /1000),
     error_rate_per_second, network_rx_bytes (normalised via /1e6),
     network_tx_bytes (normalised via /1e6), restart_penalty, latency_spike

2. `app/core/ring_buffer.py`:
   Create generic class `RingBuffer[T]`:
   - Constructor takes `maxlen: int`
   - Internal storage: `collections.deque(maxlen=maxlen)`
   - `asyncio.Lock` for thread safety
   - Methods:
     * `async def append(item: T) -> None`
     * `async def get_window(n: int) -> list[T]` — returns last n items
     * `async def get_all() -> list[T]`
     * `@property async def length() -> int`
   - Class `ServiceRingBufferRegistry` — dict[str, RingBuffer[FeatureVector]]
     with `get_or_create(service_id)` method

3. `app/core/redis_client.py`:
   Create `RedisStreamClient` class:
   - Constructor takes `redis_url: str`
   - `async def connect()` — creates `redis.asyncio.Redis` from URL
   - `async def publish_anomaly_event(event: AnomalyEvent) -> str` — XADD to
     stream "anomaly_events", returns stream entry ID
   - `async def consume_action_receipts(count=10, block_ms=1000)` — XREAD from
     "action_receipts" stream, returns list[ActionReceipt]
   - `async def close()`

Write comprehensive docstrings. Add `__all__` exports. Include type hints throughout.
```

---

### P-05 — Half-Space Trees Implementation

```
You are an ML engineer specialising in online/streaming anomaly detection.
Implement the core HST model layer for `services/ml-backend/app/ml/`.

1. `app/ml/hst_model.py`:
   Implement `HSTModelRegistry` class:
   ```
   from river.anomaly import HalfSpaceTrees
   import asyncio, logging

   class HSTModelRegistry:
       """Thread-safe registry of per-service Half-Space Trees models."""

       def __init__(self, n_trees: int, height: int, window_size: int):
           # Store hyperparams, create empty dict _models: dict[str, HalfSpaceTrees]
           # Create asyncio.Lock

       async def get_or_create(self, service_id: str) -> HalfSpaceTrees:
           # Return existing or create new HalfSpaceTrees with stored hyperparams

       async def score_and_learn(self, service_id: str, features: dict[str, float]) -> float:
           # 1. Get or create model for service_id
           # 2. score = model.score_one(features)  — BEFORE learning
           # 3. model.learn_one(features)
           # 4. Return normalised score (river HST scores can exceed 1.0 — clamp to [0,1])

       async def replace_model(self, service_id: str, new_model: HalfSpaceTrees) -> None:
           # Thread-safe replacement for rollback

       def get_all_service_ids(self) -> list[str]:
           # Return list of registered service IDs

       async def snapshot(self, service_id: str) -> bytes:
           # Pickle-serialise model for MLflow artifact storage

       async def restore(self, service_id: str, model_bytes: bytes) -> None:
           # Unpickle and replace model
   ```

2. `app/ml/adwin_detector.py`:
   Implement `ADWINDriftDetector` class wrapping `river.drift.ADWIN`:
   ```
   class ADWINDriftDetector:
       def __init__(self, delta: float = 0.002, service_id: str = ""):
           # Create ADWIN(delta=delta), store service_id, init score_history list

       def update(self, score: float) -> tuple[bool, float | None]:
           # 1. Add score to ADWIN
           # 2. Append to score_history (keep last 500)
           # 3. If self._adwin.drift_detected:
           #      change_point = self._adwin.total  # position of change
           #      Reset ADWIN
           #      Return (True, change_point)
           # 4. Return (False, None)

       def get_score_stats(self) -> dict[str, float]:
           # Return {"mean": ..., "std": ..., "max": ..., "min": ...}
           # from last 100 scores in score_history
   ```

3. `app/ml/model_manager.py`:
   Implement `MLflowModelManager`:
   ```
   class MLflowModelManager:
       def __init__(self, tracking_uri: str, registry: HSTModelRegistry):
           # mlflow.set_tracking_uri(tracking_uri)

       def start_run(self, service_id: str, hyperparams: dict) -> str:
           # Creates or gets experiment f"hst_{service_id}"
           # Starts MLflow run, logs hyperparams, returns run_id

       def log_metrics(self, run_id: str, step: int, score: float,
                       drift_count: int, event_count: int) -> None:
           # mlflow.log_metrics inside run context

       async def rollback(self, service_id: str) -> bool:
           # 1. Search MLflow Model Registry for last "Production" model
           #    for experiment f"hst_{service_id}"
           # 2. Download pickle artifact
           # 3. Call registry.restore(service_id, model_bytes)
           # 4. Return True if successful, False if no Production model found

       async def promote_to_production(self, service_id: str, run_id: str) -> None:
           # Register model, transition to "Production" stage
           # Archive previous Production version
   ```

Write unit tests in `tests/unit/test_hst_model.py`:
- test_score_returns_float_between_0_and_1
- test_learn_updates_model_state (score should increase after anomalous input)
- test_replace_model_is_thread_safe (use asyncio.gather with 50 concurrent calls)
- test_adwin_detects_shift (feed 200 scores from N(0.2,0.05), then 200 from N(0.8,0.05),
  assert drift detected within 50 samples of shift)
```

---

### P-06 — FastAPI Ingest & Prediction Endpoints  ✦ CORRECTED

```
You are a Python API engineer. Implement the REST and WebSocket API routes for the
ML backend service. All files under `services/ml-backend/app/api/`.

ARCHITECTURAL CONSTRAINTS (apply strictly):
- The /ingest/prometheus endpoint accepts JSON only — NO Snappy decompression,
  NO protobuf parsing, NO python-snappy, NO prometheus-remote-storage.
- The WebSocket gateway uses Redis Pub/Sub for fan-out, NOT an in-memory
  active_connections set (which breaks across multiple HPA replicas).

1. `app/api/routes/ingest.py`:
   Router prefix `/ingest`. Two endpoints:

   POST `/ingest/metrics`:
   - Accepts `MetricPayload` body (JSON, Content-Type: application/json)
   - Uses `FeatureExtractor.extract()` to get `FeatureVector`
   - Appends to `ServiceRingBufferRegistry`
   - Calls `HSTModelRegistry.score_and_learn()` to get anomaly_score
   - Calls `ADWINDriftDetector.update(score)` — gets (drift_detected, change_point)
   - If drift_detected: call `MLflowModelManager.rollback(service_id)` (async, non-blocking)
   - Builds `AnomalyScore` with severity from score thresholds:
     <0.5 → watch, <0.7 → warn, <0.85 → degrade, >=0.85 → critical
   - Builds `AnomalyEvent`, publishes to BOTH:
     (a) Redis XADD stream "anomaly_events" (for Decision Engine consumer group)
     (b) Redis PUBLISH channel "ws:anomaly_broadcast" (for WebSocket fan-out)
   - Persists event to TimescaleDB metric_events hypertable via asyncpg
   - Returns `AnomalyScore`

   POST `/ingest/prometheus-webhook`:
   - Accepts Alertmanager webhook JSON payload (Content-Type: application/json)
   - Body schema: Alertmanager's standard webhook format:
     {"alerts": [{"labels": {"service": "svc-a", ...}, "annotations": {...}}]}
   - For each alert, extract service label and construct MetricPayload with
     available metric fields (gracefully default missing fields to 0.0)
   - Call the same scoring pipeline as /ingest/metrics for each service
   - Returns {"ingested": N} count
   - This endpoint allows Prometheus Alertmanager to forward firing alerts as JSON
     with zero binary dependencies

2. `app/api/routes/predict.py`:
   Router prefix `/predict`.

   GET `/predict/{service_id}`:
   - Returns last AnomalyScore for service_id from Redis (XREVRANGE, count=1)
   - 404 if no data found yet

   GET `/predict/batch`:
   - Query param: `service_ids: list[str]`
   - Returns dict[str, AnomalyScore] for all requested services

3. `app/api/routes/models.py`:
   Router prefix `/models`.

   GET `/models`:
   - Returns list of registered service IDs and their MLflow experiment names

   POST `/models/{service_id}/rollback`:
   - Triggers `MLflowModelManager.rollback(service_id)`
   - Returns {"success": bool, "message": str}

   POST `/models/{service_id}/promote`:
   - Body: `{"run_id": str}`
   - Calls `MLflowModelManager.promote_to_production(service_id, run_id)`

4. `app/api/websocket.py`:
   `GET /ws/events` WebSocket endpoint — Redis Pub/Sub fan-out pattern:

   DO NOT use a module-level `active_connections` set. That approach breaks when
   FastAPI runs across multiple HPA replicas (each pod only knows its own clients).

   Instead, implement this distributed pattern:
   ```python
   @router.websocket("/ws/events")
   async def websocket_events(websocket: WebSocket):
       await websocket.accept()
       # Create a DEDICATED Redis connection for this client's Pub/Sub listener.
       # (Pub/Sub mode monopolises a connection — never reuse the shared pool.)
       pubsub_redis = redis.asyncio.Redis.from_url(settings.REDIS_URL)
       pubsub = pubsub_redis.pubsub()
       await pubsub.subscribe("ws:anomaly_broadcast", "ws:action_broadcast")
       try:
           async def listen():
               async for message in pubsub.listen():
                   if message["type"] == "message":
                       # Forward raw JSON payload to this client
                       await websocket.send_text(message["data"].decode())
           listen_task = asyncio.create_task(listen())
           # Keep alive: wait for client disconnect
           await websocket.receive_text()  # blocks until client closes
       except WebSocketDisconnect:
           pass
       finally:
           listen_task.cancel()
           await pubsub.unsubscribe()
           await pubsub_redis.aclose()
   ```

   The publishing side (in ingest.py) does:
   ```python
   await redis_client.publish("ws:anomaly_broadcast", event_json)
   ```
   All FastAPI pods subscribed to that channel receive the message instantly
   and forward it to their locally-connected WebSocket clients.

   Also subscribe to "ws:action_broadcast" — the Decision Engine publishes
   ActionReceipts to this channel after executing remediation.

Use dependency injection: `Annotated[HSTModelRegistry, Depends(get_hst_registry)]`
where `get_hst_registry` reads from `request.app.state.hst_registry`.

Also add `app/core/timescaledb_client.py`:
- `TimescaleDBClient` using asyncpg connection pool (TIMESCALEDB_URL from settings)
- `async def insert_metric_event(event: AnomalyEvent)` → INSERT INTO metric_events
- `async def query_recent(service_id: str, minutes: int = 60)` → SELECT from hypertable
  with time_bucket for aggregated history (used by LLM RAG retriever)

Write integration tests in `tests/integration/test_ingest_endpoint.py`:
- test_ingest_returns_anomaly_score (mock Redis and TimescaleDB)
- test_websocket_receives_via_pubsub (start two WebSocket clients on same pod,
  publish to Redis channel, assert both receive the message)
- test_prometheus_webhook_endpoint_accepts_alertmanager_json
```

---

## SECTION C: .NET Decision Engine

---

### P-07 — .NET Worker Service Foundation  ✦ CORRECTED

```
You are a senior C# engineer. Set up the .NET 8 Worker Service foundation for
`services/decision-engine/src/DecisionEngine/`.

ARCHITECTURAL CONSTRAINTS (apply strictly):
- There is NO Consul. Do not add Consul NuGet packages or IConsulClient anywhere.
- The Dependency Graph is built entirely from the Kubernetes API by reading
  Deployment annotations. KubernetesClient is the ONLY service discovery mechanism.
- The Decision Engine also publishes ActionReceipts to Redis Pub/Sub channel
  "ws:action_broadcast" so all FastAPI WebSocket pods receive them.

1. `Program.cs` — Host builder with:
   - AddHostedService<AnomalyConsumerWorker>()
   - AddHostedService<HealthCheckWorker>()      ← refreshes K8s annotation DAG every 60s
   - AddSingleton<DependencyGraph>()
   - AddSingleton<PolicyEvaluator>()
   - AddSingleton<ActionDispatcher>()
   - AddSingleton<RedisStreamConsumer>() (reads REDIS_URL from config)
   - AddHttpClient<YarpTrafficShifter>(client => client.BaseAddress = YARP_ADMIN_URL)
   - AddKubernetesClient() — auto-detect in-cluster config, fallback to ~/.kube/config
   - AddLogging with structured JSON format (use Microsoft.Extensions.Logging)
   - AddHealthChecks() with Redis and HTTP checks
   DO NOT register IConsulClient or any Consul-related service.

2. `appsettings.json` and `appsettings.Development.json`:
   Keys: RedisUrl, YarpAdminUrl, MlBackendUrl, KubernetesNamespace (="selfheal-apps"),
   AnomalyConsumerGroupName (="decision-engine"), BatchSize (=10), BlockMs (=1000)
   DO NOT include ConsulUrl — Consul is not used.

3. `Models/AnomalyEvent.cs` — record:
   ServiceId (string), Timestamp (long), AnomalyScore (double),
   Severity (string), DriftDetected (bool)

4. `Models/RemediationAction.cs` — record:
   ServiceId (string), Timestamp (long), ActionType (enum: Watch/Warn/Degrade/Critical),
   TargetReplicas (int?), TrafficWeightPercent (int?), Reason (string)

5. `Models/ActionReceipt.cs` — record:
   ServiceId (string), Timestamp (long), ActionType (string),
   Executor (string), Success (bool), Details (string)

6. `Models/ServiceNode.cs` — record:
   ServiceId (string), Namespace (string), DeploymentName (string),
   PodIPs (IReadOnlyList<string>), Upstreams (IReadOnlyList<string>),
   Downstreams (IReadOnlyList<string>)

7. `Infrastructure/RedisStreamConsumer.cs`:
   - Constructor takes IConfiguration, ILogger
   - Connects using StackExchange.Redis ConnectionMultiplexer
   - `async Task<IReadOnlyList<AnomalyEvent>> ConsumeAsync(CancellationToken ct)`:
     XREADGROUP GROUP "decision-engine" "consumer-1" from "anomaly_events"
     Deserialise NameValueEntry[] to AnomalyEvent records. Return list.
   - `async Task AcknowledgeAsync(string streamKey, string[] entryIds)`:
     XACK "anomaly_events" group entryIds
   - `async Task PublishActionReceiptAsync(ActionReceipt receipt)`:
     (a) XADD "action_receipts" * (for audit/persistence)
     (b) Redis PUBLISH "ws:action_broadcast" JSON-serialised receipt
         (so all FastAPI WebSocket replicas deliver it to their clients)

Use `System.Text.Json` for serialisation. All async methods accept CancellationToken.
Include XML doc comments on all public members.
```

---

### P-08 — Policy Evaluator & Dependency Graph  ✦ CORRECTED

```
You are a senior C# engineer. Implement the core decision logic for the Decision Engine.

ARCHITECTURAL CONSTRAINTS (apply strictly):
- DependencyGraph builds its DAG exclusively from Kubernetes Deployment annotations.
- There is NO Consul, no IConsulClient, no service registry of any kind.
- The annotation key is selfheal.io/upstreams with a comma-separated value
  listing the serviceIds that THIS deployment directly calls (its upstreams).

1. `Engine/PolicyEvaluator.cs`:
   ```csharp
   public enum RemediationLevel { Watch, Warn, Degrade, Critical }

   public interface IPolicyEvaluator {
       RemediationLevel Evaluate(double anomalyScore);
       RemediationAction BuildAction(AnomalyEvent evt, RemediationLevel level, ServiceNode node);
   }

   public class PolicyEvaluator : IPolicyEvaluator {
       // Evaluate: use switch expression with score thresholds
       // < 0.5 → Watch, < 0.7 → Warn, < 0.85 → Degrade, >= 0.85 → Critical

       // BuildAction: map RemediationLevel to RemediationAction:
       // Watch    → ActionType=Watch, no scaling, TrafficWeightPercent=100
       // Warn     → ActionType=Warn,  TargetReplicas=current+1, Traffic=100
       // Degrade  → ActionType=Degrade, Traffic=50 (fail over 50%), current+1 replica
       // Critical → ActionType=Critical, Traffic=0 (drain), restart pod, rollback
   }
   ```

2. `Engine/DependencyGraph.cs`  ← Kubernetes annotation-based, NO Consul:
   ```csharp
   public interface IReadOnlyDependencyGraph {
       ServiceNode? GetNode(string serviceId);
       IReadOnlyList<ServiceNode> GetUpstreams(string serviceId);
       IReadOnlyList<ServiceNode> GetDownstreams(string serviceId);
       IReadOnlyList<ServiceNode> GetAllAffected(string serviceId); // BFS both directions
   }

   public class DependencyGraph : IReadOnlyDependencyGraph {
       private readonly ConcurrentDictionary<string, ServiceNode> _nodes = new();
       private readonly IKubernetes _k8s;
       private readonly string _namespace;

       // RefreshFromKubernetesAsync(CancellationToken ct):
       //   var deployments = await _k8s.ListNamespacedDeploymentAsync(_namespace, cancellationToken: ct);
       //   foreach (var dep in deployments.Items) {
       //       string serviceId = dep.Metadata.Name;
       //       string[] upstreams = dep.Metadata.Annotations
       //           ?.GetValueOrDefault("selfheal.io/upstreams", "")
       //           .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
       //           ?? Array.Empty<string>();
       //       _nodes[serviceId] = new ServiceNode(
       //           ServiceId: serviceId,
       //           Namespace: _namespace,
       //           DeploymentName: dep.Metadata.Name,
       //           PodIPs: GetPodIPs(dep),    // query pods with app=dep.Name label
       //           Upstreams: upstreams,
       //           Downstreams: Array.Empty<string>()  // populated in second pass below
       //       );
       //   }
       //   // Second pass: compute reverse edges (downstreams)
       //   foreach (var (id, node) in _nodes) {
       //       foreach (var upstream in node.Upstreams) {
       //           if (_nodes.TryGetValue(upstream, out var upstreamNode)) {
       //               _nodes[upstream] = upstreamNode with {
       //                   Downstreams = upstreamNode.Downstreams.Append(id).ToArray()
       //               };
       //           }
       //       }
       //   }
       //
       // GetAllAffected: BFS both directions — collect all transitively reachable nodes
       // Guard against cycles using a visited HashSet<string>
   }
   ```

3. `Engine/ActionDispatcher.cs`:
   ```csharp
   public class ActionDispatcher {
       // Constructor: inject IReadOnlyDependencyGraph, YarpTrafficShifter,
       //   KubernetesExecutor, MlflowRollbackExecutor, RedisStreamConsumer, ILogger

       public async Task DispatchAsync(AnomalyEvent evt, CancellationToken ct) {
           // 1. Evaluate anomaly score → RemediationLevel
           // 2. GetNode(evt.ServiceId)
           // 3. BuildAction(evt, level, node)
           // 4. Execute based on ActionType:
           //    Watch → log only
           //    Warn  → KubernetesExecutor.ScaleAsync(+1)
           //    Degrade → YarpTrafficShifter.ShiftAsync(50%) + KubernetesExecutor.ScaleAsync(+1)
           //    Critical → YarpTrafficShifter.ShiftAsync(0%) + KubernetesExecutor.RestartPodAsync()
           //               + MlflowRollbackExecutor.TriggerRollbackAsync()
           // 5. For each downstream of failing service: KubernetesExecutor.ScaleAsync(+1)
           // 6. Build ActionReceipt, publish to Redis
       }
   }
   ```

4. Write unit tests in `tests/Engine/PolicyEvaluatorTests.cs`:
   - TestWatch: score 0.3 → RemediationLevel.Watch
   - TestWarn: score 0.6 → RemediationLevel.Warn
   - TestDegrade: score 0.75 → RemediationLevel.Degrade
   - TestCritical: score 0.92 → RemediationLevel.Critical
   - TestBoundaries: exactly 0.5, 0.7, 0.85 (boundary values → upper level)

5. Write unit tests in `tests/Engine/DependencyGraphTests.cs`:
   - TestGetAllAffectedTraversesBothDirections
   - TestCircularDependencyDoesNotInfiniteLoop
```

---

### P-09 — Kubernetes & YARP Executors

```
You are a senior C# engineer. Implement the action executors for the .NET Decision Engine.

1. `Executors/KubernetesExecutor.cs`:
   ```csharp
   public class KubernetesExecutor {
       private readonly IKubernetes _k8s;
       private readonly string _namespace;
       private readonly ILogger<KubernetesExecutor> _logger;

       public async Task ScaleDeploymentAsync(string deploymentName, int delta, CancellationToken ct) {
           // GET current Deployment, read spec.replicas, add delta (min 1, max 10)
           // PATCH spec.replicas using strategic merge patch
           // Log result
       }

       public async Task DeletePodAsync(string podName, CancellationToken ct) {
           // DELETE pod (K8s will restart via ReplicaSet controller)
           // Log pod name and timestamp
       }

       public async Task<bool> RollbackDeploymentAsync(string deploymentName, CancellationToken ct) {
           // Equivalent of `kubectl rollout undo deployment/name`
           // Use AppsV1Api: get Deployment, find previous revision in annotations
           // PATCH with rollback spec
           // Return true if rollback initiated
       }

       public async Task<IReadOnlyList<string>> GetPodIPsAsync(string deploymentName, CancellationToken ct) {
           // List pods with label selector app=deploymentName
           // Return list of status.podIP for Running pods
       }
   }
   ```

2. `Executors/YarpTrafficShifter.cs`:
   ```csharp
   public class YarpTrafficShifter {
       private readonly HttpClient _httpClient; // pointed at YARP AdminController

       public async Task ShiftTrafficAsync(string serviceId, int weightPercent, CancellationToken ct) {
           // PATCH /admin/cluster with body:
           // {"clusterId": $"cluster-{serviceId}", "weightPercent": weightPercent}
           // If weightPercent == 0: drain (no new requests to this service's pods)
           // Log the shift
       }

       public async Task RestoreTrafficAsync(string serviceId, CancellationToken ct) {
           // PATCH /admin/cluster with weightPercent=100
       }
   }
   ```

3. `Executors/MlflowRollbackExecutor.cs`:
   ```csharp
   public class MlflowRollbackExecutor {
       private readonly HttpClient _httpClient; // pointed at FastAPI ML backend

       public async Task<bool> TriggerRollbackAsync(string serviceId, CancellationToken ct) {
           // POST to FastAPI /models/{serviceId}/rollback
           // Parse response {"success": bool, "message": str}
           // Return success bool
       }
   }
   ```

4. `Workers/AnomalyConsumerWorker.cs` (BackgroundService):
   ```csharp
   protected override async Task ExecuteAsync(CancellationToken stoppingToken) {
       // Ensure consumer group "decision-engine" exists (XGROUP CREATE or ignore EXISTS)
       while (!stoppingToken.IsCancellationRequested) {
           var events = await _consumer.ConsumeAsync(stoppingToken);
           foreach (var evt in events) {
               await _dispatcher.DispatchAsync(evt, stoppingToken);
               await _consumer.AcknowledgeAsync("anomaly_events", evt.EntryId);
           }
           // Small yield to prevent tight loop on empty stream
           await Task.Delay(100, stoppingToken);
       }
   }
   ```

5. `Workers/HealthCheckWorker.cs` (BackgroundService):
   - Every 60s: calls `DependencyGraph.RefreshFromKubernetes()`
   - Logs count of registered services
```

---

## SECTION D: YARP Gateway

---

### P-10 — YARP Dynamic Configuration

```
You are a C# engineer specialising in reverse proxies. Implement the YARP Gateway service
at `services/yarp-gateway/src/YarpGateway/`.

1. `Program.cs`:
   - `builder.Services.AddReverseProxy().LoadFromMemory(routes, clusters)`
   - Register `DynamicRouteProvider` as singleton
   - Register `AdminController` — bind to localhost:5000/admin only via
     `app.Map("/admin", adminApp => adminApp.UseRouting().MapControllers())`
   - Main proxy listens on port 80

2. `Configuration/DynamicRouteProvider.cs`:
   ```csharp
   public class DynamicRouteProvider : IProxyConfigProvider {
       private volatile InMemoryConfig _config;
       private readonly object _lock = new();

       public IProxyConfig GetConfig() => _config;

       public void UpdateClusterWeight(string clusterId, string destinationId, int weightPercent) {
           lock (_lock) {
               // Clone existing clusters, find matching cluster + destination
               // Set destination Metadata["Weight"] = weightPercent.ToString()
               // Create new InMemoryConfig with updated clusters, trigger reload
               // (InMemoryConfig signals changeToken on creation)
           }
       }

       public void AddCluster(string clusterId, string destinationId, string address) {
           // Add new cluster + route dynamically (for service discovery)
       }
   }
   ```

3. `Controllers/AdminController.cs`:
   ```csharp
   [ApiController, Route("admin")]
   public class AdminController : ControllerBase {
       [HttpPatch("cluster")]
       public IActionResult PatchClusterWeight([FromBody] ClusterWeightRequest req) {
           _provider.UpdateClusterWeight(req.ClusterId, req.DestinationId, req.WeightPercent);
           return Ok(new { updated = true, clusterId = req.ClusterId });
       }

       [HttpGet("clusters")]
       public IActionResult GetClusters() {
           // Return current cluster config as JSON
       }
   }
   public record ClusterWeightRequest(string ClusterId, string DestinationId, int WeightPercent);
   ```

4. `appsettings.json` — initial static YARP config for 5 demo services:
   Routes: route-svc-a through route-svc-e with path patterns /api/{service}/{**rest}
   Clusters: cluster-svc-a through cluster-svc-e with placeholder destination addresses
   (will be overridden by DynamicRouteProvider at runtime)

5. Write unit test `tests/AdminControllerTests.cs`:
   - TestPatchWeight_Updates_Config
   - TestPatchWeight_ZeroWeight_DrainsTraffic
   Use WebApplicationFactory<Program> for integration testing.
```

---

## SECTION E: React Frontend

---

### P-11 — Vite + Tailwind + Zustand Setup

```
You are a senior React/TypeScript engineer. Set up the frontend scaffold for
`frontend/` with React 18, Vite, Tailwind CSS, and Zustand.

1. `vite.config.ts`:
   - React plugin, alias @ → src/
   - Proxy /api/ml → http://localhost:8000
   - Proxy /ws → ws://localhost:8000 (WebSocket)
   - Proxy /api/llm → http://localhost:8001

2. `tailwind.config.ts`:
   - Content: ["./src/**/*.{ts,tsx}"]
   - Extend theme: add custom colours:
     `selfheal` palette: healthy: #22c55e, degraded: #f59e0b,
     critical: #ef4444, watch: #64748b, warn: #3b82f6
   - Add animation: `pulse-slow` (2s pulse), `score-glow` (1.5s glow)

3. `src/types/service.ts`:
   ```typescript
   export type ServiceStatus = 'healthy' | 'watch' | 'warn' | 'degrade' | 'critical';

   export interface ServiceState {
     serviceId: string;
     status: ServiceStatus;
     anomalyScore: number;
     scoreHistory: Array<{ ts: number; score: number }>;
     lastActionAt: number | null;
     lastAction: string | null;
     driftDetected: boolean;
   }
   ```

4. `src/types/incident.ts`:
   ```typescript
   export interface Incident {
     id: string;
     serviceId: string;
     startedAt: number;
     resolvedAt: number | null;
     severity: ServiceStatus;
     actions: ActionReceipt[];
   }

   export interface ActionReceipt {
     serviceId: string;
     timestamp: number;
     actionType: string;
     executor: string;
     success: boolean;
     details: string;
   }
   ```

5. `src/stores/servicesStore.ts` — Zustand store:
   ```typescript
   interface ServicesStore {
     services: Record<string, ServiceState>;
     updateScore: (serviceId: string, score: number, drift: boolean, severity: ServiceStatus) => void;
     setAction: (serviceId: string, action: string) => void;
   }
   // updateScore: upsert service, push to scoreHistory (keep last 100 points)
   // Status derived from severity in the incoming event
   ```

6. `src/stores/incidentsStore.ts` — Zustand store:
   - `incidents: Incident[]`, `addAction(receipt: ActionReceipt)`, `resolveIncident(serviceId)`
   - `activeIncidents` computed: incidents where resolvedAt === null

7. `src/hooks/useWebSocket.ts`:
   ```typescript
   // Native WebSocket with exponential backoff reconnect
   // Config: initialDelay=1000, maxDelay=30000, factor=2
   // Returns: { lastMessage: WSMessage | null, status: 'connecting'|'connected'|'disconnected' }
   // On message: parse JSON, dispatch to correct store based on message.type
   // ('anomaly' → servicesStore.updateScore, 'action' → incidentsStore.addAction)
   ```

8. `src/App.tsx` — Wraps `<Layout>` with `<Dashboard>` as default route.
   Use React Router v6. Routes: / → Dashboard, /incidents → Incidents, /models → Models, /copilot → Copilot.
```

---

### P-12 — Dashboard Components

```
You are a senior React/TypeScript engineer. Build the main dashboard components
for `frontend/src/components/dashboard/`.

1. `ServiceHealthGrid.tsx`:
   - Reads from `servicesStore`
   - Renders a responsive CSS grid (3 cols on desktop, 2 on tablet, 1 on mobile)
   - Each `ServiceTile` shows:
     * Service name in bold
     * Coloured status badge (use selfheal Tailwind colours)
     * Current anomaly score as large number (0.00 format)
     * Mini sparkline of last 20 score values (use SVG path, no library needed)
     * Last action text in small grey font
     * Pulsing red border when status === 'critical'
   - Animate tile on score change using Tailwind `transition-all duration-300`

2. `AnomalyScoreChart.tsx`:
   - Uses Recharts `LineChart` with `ResponsiveContainer`
   - Props: `serviceId: string | 'all'` — if 'all', show all services as separate lines
   - X axis: timestamp formatted as HH:mm:ss
   - Y axis: 0.0 to 1.0
   - Add `ReferenceLine y={0.5}` dashed orange (warn threshold)
   - Add `ReferenceLine y={0.85}` dashed red (critical threshold)
   - Rolling window: display last 10 minutes of data
   - `Tooltip` showing exact score + severity label + timestamp
   - Legend showing service name per line with coloured dot

3. `IncidentFeed.tsx`:
   - Reads from `incidentsStore.activeIncidents`
   - Vertical scrollable list (max-height: 400px)
   - Each item shows: severity badge, service name, action taken, time ago (e.g. "2m ago")
   - New items animate in from top using CSS `@keyframes slideDown`
   - "No active incidents" empty state with green checkmark SVG

4. `DriftAlertBanner.tsx`:
   - Shows when any service has `driftDetected === true` in `servicesStore`
   - Fixed banner at top of page (z-50)
   - Orange background, warning icon, "Model drift detected in: svc-d, svc-e" text
   - Dismiss button (removes from store)
   - Auto-dismiss after 30s

All components: TypeScript strict mode, no `any`, explicit return types.
Use `memo()` on ServiceTile to prevent unnecessary re-renders.
```

---

### P-13 — D3.js Dependency Graph

```
You are a React engineer with D3.js expertise. Build the dependency graph component
for `frontend/src/components/dashboard/DependencyGraph.tsx`.

Requirements:
- Uses D3.js `forceSimulation` with `forceLink`, `forceManyBody`, `forceCenter`
- Nodes represent services fetched from GET /api/ml/predict/batch
- Edges represent dependency relationships (fetch from GET /api/ml/predict/batch
  which includes a `dependencies` field)
- Rendered as SVG inside a React component (use useRef for the SVG element)
- Node styling:
  * Circle radius 24px
  * Fill colour from ServiceStatus (use selfheal palette)
  * White service ID label centred in circle (font-size: 10px)
  * Pulsing glow animation when status === 'critical' (use SVG filter feGaussianBlur)
- Edge styling:
  * Line stroke #475569 normally
  * Amber (#f59e0b) when downstream service is critical (dependency at risk)
  * Animated dashed stroke on active incident edges
- Interactions:
  * Hover → show tooltip with current anomaly score + last action
  * Click node → navigate to /incidents?filter={serviceId}
- Resize: use ResizeObserver to update SVG width/height and re-centre force simulation
- Updates: re-run simulation on every servicesStore change
  (use useEffect with Zustand subscribe)

Use `useCallback` for D3 simulation setup to avoid recreating on every render.
D3 mutations should only touch the SVG DOM ref — never React state during simulation ticks.
```

---

### P-14 — Copilot Chat Panel

```
You are a frontend engineer. Build the Copilot chat UI for
`frontend/src/components/copilot/CopilotChatPanel.tsx`.

Component requirements:
- Full-height panel layout: message list (flex-1, overflow-y-auto) + input area (fixed bottom)
- Message bubbles:
  * User: right-aligned, indigo background
  * Assistant: left-aligned, dark grey background, renders Markdown using `react-markdown`
  * Loading: animated three-dot spinner while streaming
- Input: `<textarea>` (auto-resize, max 5 rows), send on Enter (Shift+Enter = newline)
  plus Send button with paper-plane SVG icon
- Streaming: use `fetch()` with `ReadableStream` to the `/api/llm/chat` endpoint
  * Parse SSE `data:` lines
  * Append tokens to the last assistant message as they arrive
  * Show typing cursor (blinking `|`) at end of streaming message
- Suggested prompts shown when chat is empty (click to populate input):
  * "Why is service-d failing right now?"
  * "Summarise the last 3 incidents"
  * "What anomalies happened in the last hour?"
  * "Generate a post-mortem for the last critical event"
- Clear chat button in header
- Copy button on each assistant message (copies plain text, not markdown)

Also create `src/pages/Copilot.tsx`:
- Split layout: left 60% = CopilotChatPanel, right 40% = PostMortemCard list
- PostMortemCard shows: incident ID, affected service, summary text, timestamp
- Fetch post-mortems from GET /api/llm/postmortem on load
```

---

## SECTION F: ML Pipeline Scripts

---

### P-15 — SMD Dataset Preprocessing

```
You are a data engineer. Implement the SMD dataset preprocessing pipeline
in `datasets/smd/preprocess.py` and `ml-pipeline/scripts/warm_up_hst.py`.

`datasets/smd/preprocess.py`:
- Takes CLI arg `--input-dir` (path to raw SMD data) and `--output-dir`
- SMD files are in `train/` and `test/` subdirectories, named machine-{x}-{y}.txt
  and corresponding test_label/machine-{x}-{y}.txt for ground-truth labels
- Column names: SMD has 38 unlabelled columns. Map first 7 to our canonical features:
  col0=cpu_rate, col1=memory_used_fraction, col2=network_rx, col3=network_tx,
  col4=disk_read, col5=disk_write, col6=requests (proxy for latency_p99)
  Remaining cols: keep as feature_7 through feature_37
- Normalise each feature to [0,1] using min-max from training split
  Save normalisation params to `output_dir/normalization_params.json`
- Output: `output_dir/train/{entity_id}.parquet` and `output_dir/test/{entity_id}.parquet`
  where each parquet has columns: timestamp (int, row index), all feature cols,
  plus `is_anomaly` (bool, from label file, 0 in train split)
- Print progress: "Processed entity machine-{x}-{y}: {rows} rows, {anomaly_pct}% anomalies"

`ml-pipeline/scripts/warm_up_hst.py`:
- CLI args: --entity (e.g. machine-1-1), --n-trees (default 25), --height (default 15),
  --window-size (default 250), --mlflow-uri (default http://localhost:5001)
- Load train parquet for entity
- Initialise `mlflow.set_experiment(f"hst_{entity}")`, start run, log hyperparams
- Stream rows through HST: for each row → hst.score_one(features) then hst.learn_one(features)
- Every 500 rows: mlflow.log_metrics(step=i, mean_score=..., max_score=...)
- After training, evaluate on test split:
  * Score each test row (without learn_one)
  * Compute precision, recall, F1 at threshold 0.7
  * Log final metrics to MLflow
- Pickle the trained HST model → mlflow.log_artifact("hst_model.pkl")
- Print summary: entity, rows trained, test F1 score, MLflow run ID
```

---

### P-16 — NAB Benchmarking

```
You are an ML engineer. Implement NAB benchmark evaluation in
`ml-pipeline/scripts/run_nab_benchmark.py` and
`ml-pipeline/notebooks/02_nab_benchmarking.ipynb`.

`run_nab_benchmark.py`:
- CLI args: --nab-dir (path to NAB/data/), --mlflow-run-id (optional, loads model),
  --threshold (default 0.7), --output-csv (default nab_results.csv)
- Target NAB files: all CSVs in `realKnownCause/` and `realAWSMetrics/` subdirectories
  (these match IT operations context)
- For each CSV file:
  * Load NAB label JSON from NAB/labels/combined_windows.json
  * Stream rows through HST: score each row
  * Detect anomaly windows: contiguous rows where score > threshold
  * Compare detected windows to label windows
  * Compute: TP, FP, FN per file
- Aggregate across all files:
  * Standard NAB score formula: sum(sigma * scoreTP - FP_cost * FP_count) / perfect_score
    Use standard profile: sigma=1.0, FP_cost=0.11, FN_cost=1.0
  * Print: "NAB Score (Standard): {score:.3f}"
  * Target: score > 0.55 (competitive baseline for streaming detectors)
- Write per-file results to output CSV: filename, TP, FP, FN, precision, recall, NAB_contribution
- If --mlflow-run-id provided: log NAB score to that MLflow run

`notebooks/02_nab_benchmarking.ipynb`:
- Cells: imports → load data → visualise 3 example time series with score overlay
  → run benchmark → plot precision-recall curve → compare HST vs Isolation Forest baseline
  → print final NAB score
```

---

## SECTION G: Infrastructure & Kubernetes

---

### P-17 — Helm Chart Core Templates

```
You are a DevOps engineer. Write Helm chart templates for
`infrastructure/helm/self-healing-framework/`.

1. `Chart.yaml`:
   name: self-healing-framework, version: 0.1.0, appVersion: "1.0.0",
   dependencies: (none — all services are local)

2. `values.yaml` — comprehensive default values:
   - Per service: image.repository, image.tag, image.pullPolicy, replicas,
     resources.requests (cpu: 250m, memory: 256Mi), resources.limits (cpu: 500m, memory: 512Mi)
   - Services: mlBackend, decisionEngine, yarpGateway, llmCopilot, frontend
   - Redis: enabled: true, persistence.size: 5Gi
   - Mlflow: enabled: true, persistence.size: 10Gi
   - Global: namespace: selfheal-system, imagePullSecret: ""

3. `templates/ml-backend/deployment.yaml`:
   - 2 replicas (from values), rolling update strategy maxSurge=1 maxUnavailable=0
   - Container: image from values, ports 8000, envFrom ConfigMap
   - LivenessProbe: GET /health, initialDelay=30s, period=10s
   - ReadinessProbe: GET /ready, initialDelay=10s, period=5s
   - Resources from values

4. `templates/ml-backend/configmap.yaml`:
   - All env vars from values: REDIS_URL, MLFLOW_TRACKING_URI, etc.

5. `templates/ml-backend/hpa.yaml`:
   - minReplicas: 2, maxReplicas: 6
   - Custom metric: `redis_stream_length{stream="anomaly_events"}` > 100 → scale up
   - Fallback CPU metric: targetAverageUtilization: 70

6. `templates/decision-engine/deployment.yaml`:
   - 2 replicas, same pattern as ml-backend
   - ServiceAccount: decision-engine-sa (defined separately in rbac/)
   - Additional env: KUBERNETES_NAMESPACE from fieldRef: metadata.namespace

7. `templates/decision-engine/rbac.yaml`:
   - ServiceAccount: decision-engine-sa
   - ClusterRole: get/list/watch/patch Deployments; get/list/watch Pods; delete Pods
   - ClusterRoleBinding: binds SA to ClusterRole

8. `templates/yarp-gateway/service.yaml`:
   - Type: LoadBalancer (or NodePort for Minikube)
   - Ports: 80 (proxy), 5000 (admin, ClusterIP only — internal)

Write valid Kubernetes YAML. Use `{{ .Values.xxx }}` templating throughout.
Use `tpl` for image tag: `{{ .Values.mlBackend.image.repository }}:{{ .Values.mlBackend.image.tag }}`
```

---

### P-18 — Chaos Mesh Experiment Manifests

```
You are a DevOps/SRE engineer. Write Chaos Mesh experiment manifests for
`infrastructure/helm/self-healing-framework/templates/chaos-mesh/`.

1. `pod-kill.yaml` — PodChaos:
   - Kind: PodChaos, mode: one, action: pod-kill
   - Selector: namespace selfheal-apps, label app=service-d
   - Duration: "30s", schedule: one-shot (not cron)
   - Expected outcome: Decision Engine detects, restarts pod within 60s

2. `network-delay.yaml` — NetworkChaos:
   - Kind: NetworkChaos, action: delay
   - Selector: service-b (order processing)
   - latency: "200ms", jitter: "50ms", correlation: "25"
   - Duration: "120s"
   - Expected outcome: latency_p99 spike → HST score > 0.7 → Degrade action

3. `memory-stress.yaml` — StressChaos:
   - Kind: StressChaos
   - Selector: service-a
   - stressors: memory: workers=1, size: "256MB"
   - Duration: "90s"
   - Expected outcome: memory_pressure feature spikes → HST detects → Warn action

4. `scripts/run-chaos-experiment.sh`:
   - Accepts arg: --experiment (pod-kill|network-delay|memory-stress)
   - Applies the corresponding manifest
   - Polls `GET http://localhost:8000/predict/{service}` every 5s for 3 minutes
   - Logs score to CSV: timestamp, service_id, score, severity
   - Prints: "Max score reached: 0.XX at T+Xs"
   - After 3 minutes: kubectl delete the chaos resource
   - Prints recovery time: "Service recovered (score < 0.5) at T+Ys"
```

---

## SECTION H: LLM Copilot Service

---

### P-19 — LangChain RAG Pipeline  ✦ CORRECTED

```
You are a Python ML engineer specialising in LLM applications. Implement the RAG
telemetry pipeline for `services/llm-copilot/app/`.

ARCHITECTURAL CONSTRAINTS (apply strictly):
- Do NOT use FAISS. The vector index lives in TimescaleDB using the pgvector extension.
- All telemetry embeddings are stored in the `telemetry_embeddings` table
  (already created by infrastructure/db/init.sql with ivfflat index on embedding vector(384)).
- Use `asyncpg` for all database operations (async, connection-pool based).
- The `pgvector` Python package provides the `vector` type adapter for asyncpg.
- Add dependencies: asyncpg, pgvector, sentence-transformers, langchain, langchain-openai

1. `rag/indexer.py` — `TelemetryIndexer` class:
   - Uses `sentence-transformers` model "all-MiniLM-L6-v2" for embeddings (384-dim)
   - Connects to TimescaleDB via asyncpg pool (TIMESCALEDB_URL from settings)
   - Registers pgvector codec: `await register_vector(conn)` on each connection
   - `TelemetryDocument` dataclass: doc_id, service_id, timestamp, anomaly_score,
     severity, action_taken, raw_text (formatted summary string)
   - `async def index_event(event: AnomalyEvent) -> None`:
     * Format raw_text: "At {iso_time}, {service_id} anomaly score {score:.2f}
       ({severity}). Action: {action}. Drift: {drift}."
     * embedding = model.encode(raw_text)  → numpy array shape (384,)
     * INSERT INTO telemetry_embeddings (service_id, content, embedding)
       VALUES ($1, $2, $3)  where $3 is the numpy array (pgvector handles serialisation)
   - Background startup task: subscribe to Redis Pub/Sub channel "ws:anomaly_broadcast",
     deserialise each message as AnomalyEvent, call index_event()
     (Pub/Sub used here so the copilot service stays in sync without a separate Stream consumer group)

2. `rag/retriever.py` — `TelemetryRetriever` class:
   - Takes asyncpg pool in constructor
   - `async def retrieve(query: str, top_k: int = 5) -> list[TelemetryDocument]`:
     * embedding = model.encode(query)
     * SQL: SELECT id, service_id, content, created_at,
              embedding <-> $1 AS distance
            FROM telemetry_embeddings
            ORDER BY embedding <-> $1
            LIMIT $2
     * Returns list of TelemetryDocument ordered by semantic similarity
   - `async def retrieve_for_service(service_id: str, top_k: int = 10)`:
     * Same query with additional WHERE service_id = $3 filter
     * Then ORDER BY created_at DESC LIMIT top_k (most recent for that service)
   - `async def retrieve_time_range(start: datetime, end: datetime) -> list[TelemetryDocument]`:
     * JOIN with metric_events hypertable for time-bounded historical queries
     * Useful for post-mortem generation ("what happened between T1 and T2?")

3. `rag/prompts.py` — Prompt templates as constants:
   - `RCA_SYSTEM_PROMPT`: "You are an expert SRE. Analyse the telemetry and identify
     root cause. Be concise. Format: Root Cause / Evidence / Confidence Level"
   - `POSTMORTEM_SYSTEM_PROMPT`: Structured post-mortem template
   - `COPILOT_SYSTEM_PROMPT`: Conversational assistant prompt with tool descriptions

4. `chains/rca_chain.py`:
   - Uses LangChain `ChatOpenAI` (or `ChatAnthropic`) with streaming=True
   - `async def analyse(service_id: str, retriever: TelemetryRetriever) -> AsyncGenerator[str, None]`:
     * Retrieve top 8 docs for service
     * Format as context string
     * Stream response from LLM

5. `api/chat.py`:
   - `POST /chat` with body `{"message": str, "service_id": str | null}`
   - Returns `StreamingResponse` (SSE format: "data: {token}\n\n")
   - Uses copilot chain if no service_id, RCA chain if service_id provided
```

---

## SECTION I: CI/CD Pipelines

---

### P-20 — GitHub Actions Workflows

```
You are a DevOps engineer. Write all GitHub Actions CI/CD workflows for
`.github/workflows/`.

1. `ci-ml-backend.yml` — triggers on: push to any branch, paths: services/ml-backend/**
   Jobs:
   a. lint-and-test:
      - runs-on: ubuntu-latest
      - steps: checkout, setup-python 3.11, install uv, uv sync --frozen,
        run ruff check (lint), run ruff format --check, run pytest tests/ -v --cov=app --cov-report=xml
      - Upload coverage to codecov
   b. docker-build:
      - needs: lint-and-test, runs only on push to main
      - Login to Docker Hub, docker build, push with tags: latest + ${{ github.sha }}

2. `ci-dotnet-engine.yml` — triggers on: push, paths: services/decision-engine/**
   Jobs:
   a. build-and-test:
      - runs-on: ubuntu-latest
      - steps: checkout, setup-dotnet 8.x, dotnet restore, dotnet build --no-restore,
        dotnet test --no-build --logger "trx;LogFileName=test-results.trx" --collect "Code coverage"
      - Upload test results artifact
   b. docker-build: same pattern as above

3. `ci-frontend.yml` — triggers on: push, paths: frontend/**
   Jobs:
   a. lint-and-test:
      - runs-on: ubuntu-latest
      - steps: checkout, setup-node 20, pnpm install --frozen-lockfile,
        pnpm lint, pnpm typecheck, pnpm test --run (Vitest)
   b. e2e:
      - needs: lint-and-test
      - Install Playwright: pnpm exec playwright install --with-deps
      - Start mock backend (uses seed-demo-data.py with --mock flag)
      - pnpm exec playwright test
      - Upload Playwright report

4. `ci-k8s-manifests.yml` — triggers on: push, paths: infrastructure/**
   Steps: install kubeval + helm lint, helm template | kubeval --strict

5. `cd-deploy-staging.yml` — triggers on: push to main (all CI jobs passed)
   Steps: checkout, install kubectl + helm, configure kubeconfig from secret,
   helm upgrade --install with --set image tags from github.sha,
   kubectl rollout status -n selfheal-system deployment/ml-backend --timeout=5m

All workflows: set concurrency group to cancel in-progress on new push.
```

---

### P-21 — End-to-End Integration Test

```
You are a QA engineer. Write a comprehensive end-to-end integration test suite that
validates the complete self-healing loop. Create `tests/e2e/test_self_healing_loop.py`.

Use pytest-asyncio. The test suite requires the full docker-compose stack running.

Tests to implement:

1. `test_metric_ingestion_returns_anomaly_score`:
   POST synthetic ServiceMetrics for "test-svc" to /ingest/metrics
   Assert response has anomaly_score (float), severity (str), service_id == "test-svc"

2. `test_websocket_streams_after_ingest`:
   Open WebSocket to /ws/events
   POST metric payload
   Assert WS message received within 2s with matching service_id

3. `test_high_score_triggers_redis_event`:
   POST metrics crafted to produce score > 0.85:
   (cpu_rate=0.99, memory_pressure=0.95, error_rate=0.8, restart_count=5)
   XREAD from "anomaly_events" stream
   Assert event published with severity == "critical"

4. `test_adwin_drift_detected_after_distribution_shift`:
   POST 300 "normal" metrics (score should stay ~0.2)
   POST 100 "anomalous" metrics (score should jump to ~0.9)
   GET /predict/test-svc
   Assert drift_detected == True within last 50 events

5. `test_model_rollback_endpoint`:
   POST /models/test-svc/rollback
   Assert response {"success": true} (mock MLflow or use real if available)

6. `test_full_loop_with_chaos` (mark as slow, skip in CI unless --run-slow flag):
   Apply pod-kill chaos to service-d in Minikube
   Poll /predict/service-d every 5s for up to 120s
   Assert: score > 0.85 detected within 60s
   Assert: score < 0.5 (recovery) within 120s of peak
   Assert: ActionReceipt published in "action_receipts" stream

Add fixture: `@pytest.fixture(scope="session") async def http_client()` using httpx.AsyncClient
Add fixture: `@pytest.fixture(scope="session") async def redis_client()` using redis.asyncio
```

---

### P-22 — Prometheus Custom Metrics

```
You are a Python observability engineer. Add custom Prometheus metrics to the
ML backend service at `services/ml-backend/app/`.

Add to `app/main.py` (or a new `app/core/metrics.py`):

Define these prometheus_client metrics:
- `anomaly_score_gauge` = Gauge('selfheal_anomaly_score', 'Current anomaly score',
  ['service_id'])
- `drift_events_counter` = Counter('selfheal_drift_events_total', 'Drift detections',
  ['service_id'])
- `ingest_latency` = Histogram('selfheal_ingest_duration_seconds',
  'Ingest endpoint latency', buckets=[.005, .01, .025, .05, .1, .25, .5, 1])
- `active_models_gauge` = Gauge('selfheal_active_models', 'Number of HST model instances')
- `rollback_counter` = Counter('selfheal_model_rollbacks_total', 'MLflow rollbacks', ['service_id'])

Update `app/api/routes/ingest.py`:
- Wrap handler with `@ingest_latency.time()` decorator
- After scoring: `anomaly_score_gauge.labels(service_id=...).set(score)`
- On drift: `drift_events_counter.labels(service_id=...).inc()`

Update `app/api/routes/health.py` GET /metrics:
- Return `generate_latest()` from prometheus_client with media type
  text/plain; version=0.0.4; charset=utf-8

Update `infrastructure/helm/self-healing-framework/templates/monitoring/`:
Create `servicemonitor.yaml` — Prometheus Operator ServiceMonitor resource pointing
at ml-backend port 8000 path /metrics with scrapeInterval 15s.

Create `infrastructure/helm/self-healing-framework/templates/monitoring/grafana-dashboards/`
`selfheal-overview.json` — Grafana dashboard JSON (use grafonnet-lib format) with 4 panels:
- Panel 1: Time series of selfheal_anomaly_score per service (multi-line)
- Panel 2: Rate of selfheal_drift_events_total (bar chart, last 1h)
- Panel 3: selfheal_ingest_duration_seconds P95 (stat panel)
- Panel 4: selfheal_model_rollbacks_total over time (bar)
```

---

### P-23 — Dockerfile Optimisation

```
You are a DevOps engineer specialising in container image optimisation.
Write production-ready Dockerfiles for all services.

1. `services/ml-backend/Dockerfile`:
   Multi-stage build:
   Stage 1 (builder): python:3.11-slim, install uv, copy pyproject.toml,
   uv sync --frozen --no-install-project, copy app/, uv sync --frozen
   Stage 2 (runtime): python:3.11-slim, copy .venv from builder,
   copy app/, create non-root user "appuser" (uid 1000),
   HEALTHCHECK: curl -f http://localhost:8000/health || exit 1
   CMD: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

2. `services/decision-engine/Dockerfile`:
   Multi-stage:
   Stage 1: mcr.microsoft.com/dotnet/sdk:8.0-alpine, COPY *.sln *.csproj,
   dotnet restore, COPY src/, dotnet publish -c Release -o /app/publish
   Stage 2: mcr.microsoft.com/dotnet/aspnet:8.0-alpine, copy from builder,
   non-root user, HEALTHCHECK: wget -q http://localhost:5002/health -O /dev/null
   ENTRYPOINT: ["dotnet", "DecisionEngine.dll"]

3. `services/yarp-gateway/Dockerfile`:
   Same pattern as decision-engine but port 80.
   Add: ENV ASPNETCORE_URLS=http://+:80

4. `frontend/Dockerfile`:
   Stage 1 (builder): node:20-alpine, install pnpm via corepack,
   copy package.json pnpm-lock.yaml, pnpm install --frozen-lockfile,
   copy src/ vite.config.ts tsconfig.json index.html tailwind.config.ts,
   pnpm build
   Stage 2 (runtime): nginx:alpine, copy dist/ from builder to /usr/share/nginx/html/,
   copy nginx.conf, expose 80
   `nginx.conf`: single-page app config — try_files $uri $uri/ /index.html,
   proxy_pass /api/ml → ml-backend:8000, /ws → ml-backend:8000 (WebSocket upgrade headers)

5. `.dockerignore` (shared root): node_modules, .venv, bin, obj, __pycache__,
   *.pyc, .git, .env, mlflow.db, mlflow-artifacts, datasets/*/raw
```

---

### P-24 — Final: Pre-commit & Code Quality

```
You are a DevOps engineer. Set up code quality tooling for the monorepo.

1. `.pre-commit-config.yaml`:
   repos:
   - repo: https://github.com/astral-sh/ruff-pre-commit, rev: v0.4.0
     hooks: [ruff (--fix), ruff-format]
   - repo: https://github.com/pre-commit/mirrors-mypy, rev: v1.9.0
     hooks: [mypy] files: services/ml-backend/
   - repo: https://github.com/pre-commit/pre-commit-hooks
     hooks: [trailing-whitespace, end-of-file-fixer, check-yaml, check-json,
             check-merge-conflict, no-commit-to-branch (--branch main)]
   - repo: local
     hooks:
       - id: dotnet-format, name: dotnet format, language: system,
         entry: dotnet format services/decision-engine --verify-no-changes
         types: [c#], pass_filenames: false
       - id: ts-lint, name: TypeScript lint, language: node,
         entry: pnpm --filter frontend lint, pass_filenames: false

2. `services/ml-backend/pyproject.toml` tool sections:
   [tool.ruff]: line-length=100, target-version="py311", select=["E","F","I","UP","B"]
   [tool.mypy]: strict=true, python_version="3.11"
   [tool.pytest.ini_options]: asyncio_mode="auto", testpaths=["tests"],
     addopts="-v --tb=short"

3. `frontend/vitest.config.ts`:
   Extends vite.config.ts, adds test config:
   environment: "jsdom", setupFiles: ["src/test/setup.ts"],
   coverage: {provider: "v8", reporter: ["text","html"], include: ["src/**/*.{ts,tsx}"]}

4. `frontend/src/test/setup.ts`:
   import "@testing-library/jest-dom"
   Mock ResizeObserver (D3 DependencyGraph needs it)
   Mock WebSocket with a minimal class that stores sent messages

5. Write `tests/unit/test_feature_extractor.py`:
   - test_extract_computes_memory_pressure (memory_bytes=1e9, limit=2e9 → pressure=0.5)
   - test_extract_normalises_latency (latency_p99_ms=500 → normalised=0.5)
   - test_extract_raises_on_missing_keys
   - test_latency_spike_flag (>500ms → latency_spike=1.0)
   - test_restart_penalty_capped_at_1 (restart_count=10 → penalty=1.0 not 2.0)

Run `pre-commit install` after creating this file and verify all hooks pass on a
test commit.
```

---

## Dataset Decision Summary (for reference when running P-15 and P-16)

**Primary: SMD (Server Machine Dataset)**
- 28 entities × 38 features — closest match to Prometheus multivariate telemetry
- Ground truth labels for precision/recall evaluation
- Stream row-by-row through `river` HST

**Benchmark: NAB (Numenta Anomaly Benchmark)**
- Purpose-built for streaming detectors — gives published, comparable NAB Score
- Use `realKnownCause/` and `realAWSMetrics/` subsets (≈ 30 files, IT ops context)
- Target: NAB Score Standard Profile > 0.55 (competitive for online algorithms)

**Rejected: Multi-Source Observability** — complex multi-modal alignment required before HST can consume it; better for Phase 2 research.

**Rejected: Alibaba Trace** — no anomaly labels; too large (TB-scale); trace-focused rather than metric-focused.
