# ml-backend

FastAPI service that runs Component 1 (the anomaly detector: EWMA smoothed PCA reconstruction error
with a POT threshold) and Component 2 (CADAL dynamic model updating with operator queries) live, on
a replay of real SMD telemetry, and serves both to the React dashboard.

The ML code is not copied here: `app/core/pipeline_path.py` puts `ml-pipeline/` on `sys.path`, so
the backend runs exactly the evaluated `DynamicModelManager`.

## Run the demo (PowerShell)

```powershell
# 1. Database and message bus (TimescaleDB on 5433, Redis 7 on 6380)
docker compose -f infrastructure/local/docker-compose.demo.yml up -d

# 2. Backend
cd services/ml-backend
uv sync
uv run uvicorn app.main:app --port 8002

# 3. Frontend (second terminal)
cd frontend
pnpm dev        # http://localhost:5173, proxies /api and /ws to :8002
```

`GET http://localhost:8002/api/health` should report `"db": true, "redis": true`. If Docker isn't
running, the backend still starts: it falls back to an in-memory store and an in-process bus and
logs a warning, so the UI keeps working.

## What runs

Six demo services. Each warms up on its SMD machine's train split, then replays a 6000-row window of
that machine's test split, forward and then backward, so the replay can run indefinitely:

| Service | SMD entity, window start | Role in the demo |
|---|---|---|
| service-a-auth | machine-3-8, row 3000 | background (a drift check every ~3 min) |
| service-b-orders | machine-3-10, row 15000 | **deploy** → promote |
| service-c-inventory | machine-1-2, row 12000 | **silent change** → ask the operator |
| service-d-shipping | machine-3-8, row 0 | background |
| service-e-payments | machine-1-2, row 15000 | **incident** → no change, resume |
| service-f-search | machine-3-10, row 3000 | background |

How the windows were chosen:
- Each (machine, start row) was replayed offline for four passes (about 13 minutes of demo time) with
  nothing injected, counting alarms, drift checks and decisions. Most windows open a drift check
  every 20 to 40 seconds, because their score level varies across the window. Only the Orders,
  Inventory and Payments windows stay quiet, which is what you want on a service you inject into.
- Each scenario was then injected at five different points of each quiet window. Deploy promoted at
  all five on all three windows. A silent change on Inventory asked at all five. An incident on
  Payments resumed at four of five (the fifth was injected right after warm-up).
- Finally the whole script was run three times against the live backend at 60 events/s, each
  round after a reset: deploy → promote in 24 s, silent → ask in 29 s, answer → promote, and
  rollback, identically every time.
- Other combinations still run and show real behaviour, but are less predictable. A deploy on the
  background services can be held, for example, because some of their metrics keep trending ("still
  moving") and CADAL won't learn a regime that hasn't settled.
- `scripts/demo_preflight.py [--reset]` checks the stack and that the three demo services are calm.

**Pacing:** `DEMO_SAMPLES_PER_DAY=1440` is SMD's own one sample a minute, so the lifecycle runs with
the evaluated lengths. The replay runs at 60 events/s, 60x real time, so a one-day quarantine closes
in about 24 s on stage.

Demo injections (`POST /api/demo/{service}/{kind}`):

| kind | What it does | Expected outcome |
|---|---|---|
| `deploy` | Persistent level shift on some metrics, plus a deployment change event | `concept_drift` → **promote** (learned) |
| `silent_change` | Persistent level and spread change with no change event | `ambiguous` → **ask** the operator |
| `incident` | Spike on ~1/8 of the metrics for half a lifecycle day (720 events, ~12 s; `DEMO_INCIDENT_EVENTS`) | `no_change` → **resume** (or `incident` → **hold**); not learned. Click **Check** if no drift check opens by itself. A day-long incident would be indistinguishable from a new normal and can be re-baselined away: a documented limitation |

## Live mode: Online Boutique on Kubernetes

Instead of replaying SMD, the backend can score Google's Online Boutique running on a local
minikube cluster. Nothing is simulated there: telemetry comes from Prometheus, deployment events
come from the Kubernetes API, and faults are real Chaos Mesh experiments.

```powershell
# 1. cluster: minikube profile "sharp" + kube-prometheus-stack + Chaos Mesh + Online Boutique v0.10.7,
#    Prometheus forwarded to localhost:9090 (first run pulls about 3 GB of images)
powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/up.ps1

# 2. let it run ~1 hour untouched, so the warm-up window is clean steady traffic

# 3. backend in live mode (same port, the frontend needs no change)
cd services/ml-backend
$env:TELEMETRY_MODE = "prometheus"; uv run uvicorn app.main:app --port 8002

# 4. check
uv run python scripts/demo_preflight.py          # detects live mode
```

What happens:
- **Services.** Every Online Boutique Deployment except the load generator becomes a service. Its
  id is the Deployment's `app` label.
- **Features.** Each service has 7 features, defined in `app/prom.py`: cpu, memory, network rx/tx,
  CPU throttling, restarts and ready ratio. They are scraped every 5 s.
- **Warm-up.** Each service warms up on its own last `LIVE_WARMUP_MINUTES` of Prometheus history.
- **Pacing.** One lifecycle "day" is `LIVE_LIFECYCLE_DAY_MINUTES` = 30 min, so a quarantine
  closes 30 min after it opens.
- **Rollouts.** A Kubernetes watcher turns real rollouts into deployment change events, one per
  Deployment generation.
- **Controls.** The Model lifecycle page shows real-action buttons instead of synthetic injections:
  Rollout (a real rolling update), CPU (Chaos Mesh stress), Kill pod, and Check, plus Traffic x3 and
  Baseline for the load generator. The same actions are available as `POST /api/live/{service}/{action}`.

**Warm-up quality matters.** The warm-up window teaches each model what normal is.
- If the window contains startup crash loops, a rollout or a chaos fault, that becomes "normal".
  The threshold then rises (once to about 0.99), and services alarm at rest or miss real faults.
- Start the backend only after an hour of untouched traffic.
- Don't restart it within an hour of injecting anything.

**Chaos campaign and evaluation** (real faults with ground truth):
```powershell
uv run python scripts/chaos_campaign.py --delay-minutes 0 --warmup-minutes 30   # ~2 h, 3 services x 4 faults
cd ../../ml-pipeline
uv run python evaluate_live_chaos.py outputs/live_chaos/<run>   # detection, time to detect, false alarms, learned incidents
```
Stop the cluster with `infrastructure/online-boutique/down.ps1`. Nothing is deleted.

## Configuration (env or `.env`)

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql://postgres:selfheal@localhost:5433/selfheal` |
| `REDIS_URL` | `redis://localhost:6380` |
| `DETECTOR` / `THRESHOLD_METHOD` | `pca_s5` / `pot` |
| `REPLAY_EVENTS_PER_SEC` | `60` |
| `DEMO_SAMPLES_PER_DAY` | `1440` |
| `REPLAY_WINDOW_ROWS` | `6000` (`0` replays the whole test split, real anomalies included) |
| `QUERY_TTL_EVENTS` | `18000` (~5 min to answer a query on stage) |
| `TELEMETRY_MODE` | `replay` (or `prometheus` for live Online Boutique) |
| `PROMETHEUS_URL` / `K8S_NAMESPACE` | `http://localhost:9090` / `online-boutique` |
| `LIVE_SCRAPE_SECONDS` / `LIVE_LIFECYCLE_DAY_MINUTES` | `5` / `30` |
| `LIVE_WARMUP_MINUTES` / `LIVE_MIN_WARMUP_MINUTES` | `60` / `10` |
| `START_REPLAY` / `USE_BACKING_SERVICES` | `true` / `true` (tests set both false) |

## REST API (`/api`)

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | store kind, db/redis status, tick, speed |
| GET | `/services` | `ServiceHealth[]`, plus `phase, alarm, modelVersion, openQueries, smdEntity` |
| GET | `/services/{id}/scores?limit=` | `[{step, score, alarm, threshold}]` |
| GET | `/dashboard/summary` | stat counts, a 30 min `anomalyTrend` from TimescaleDB, table row counts |
| GET | `/models` | `ModelRun[]`, plus `detector, thresholdMethod, phase, productionVersion, versionCount, rebaselined, openQueries, lastDecision` |
| GET | `/models/{id}` | the `ModelRun` fields, plus `versions, transitions, decisions, queries` |
| POST | `/models/{id}/promote` | body `{version?, operator}`; verified manual promotion |
| POST | `/models/{id}/rollback` | body `{version?, operator}`; by default undoes the most recent promotion |
| POST | `/models/{id}/validity-check` | opens an operator-triggered quarantine |
| GET | `/lifecycle/decisions?service_id=&limit=` | the decision log, newest first |
| GET | `/queries?status=open` | operator queries |
| POST | `/queries/{id}/answer` | body `{answer: "new_normal" \| "incident", operator}` |
| GET | `/demo/state` | per-service step and active injections |
| POST | `/demo/{id}/{deploy\|silent_change\|incident}` | injects a scenario |
| POST | `/demo/speed` | body `{eventsPerSec?, paused?}` |
| POST | `/demo/reset` | rebuilds the fleet from scratch |
| GET | `/logs?q=&since=&until=&before=&limit=` | `{lines, hasMore}`: the newest `limit` matching log lines, oldest first. Page back with `before=<oldest time>` |
| GET | `/logs/histogram?q=&since=&until=` | `{bucketSeconds, buckets: [{time, info, warn, error}]}` for the strip above the log table |
| GET | `/logs/services` | `[{service, source, count}]`, every service that has logged |

Errors: 404 for an unknown service, version or query; 409 for a conflict (the query was already
answered, a decision is pending, or there is no version to roll back to); 422 for an invalid body.

## WebSocket `/ws/events`

The envelope is `{type, service_id, ts, data}`. On connect the client gets one `snapshot`
(`{services, queries}`), then:

| type | data |
|---|---|
| `anomaly_score` | `step, score` (0.5 = the calibrated threshold), `alarm, severity, version, phase, threshold` (every 10th event per service) |
| `quarantine_opened` | `trigger` (drift_up, drift_down, change_event, scheduled, operator) and the window |
| `change_observed` | the change event that reached the lifecycle |
| `lifecycle_decision` | `verdict, action, reason, evidence, query_id` |
| `operator_query` | `query_id, question, reason, evidence, expires_step` |
| `query_answered` / `query_expired` | the query with its `answer` and `operator` |
| `model_transition` | `transition` (register, promote, rollback, checkpoint), `from_version, to_version, reason, evidence` |
| `demo_injection`, `demo_speed`, `demo_reset` | presenter controls |
| `log` | one log line (`id, time, service, serviceId, source, level, message, attrs`), see Logs below. Published to Redis Pub/Sub only, not to the `anomaly_events` stream |

Every message is also published to Redis Pub/Sub `ws:anomaly_broadcast` and appended to the Redis
Stream `anomaly_events` (maxlen 20000), where the Decision Engine will consume it.

## Logs

The Logs page (`/logs` in the dashboard, Railway style) reads one stream that three sources feed
(`app/logs.py`):

| Source (`source`) | Service shown | What |
|---|---|---|
| `container` | `TimescaleDB`, `Redis` | `docker logs -f` of the demo stack's containers (names in `LOG_CONTAINERS`). Resumes after a restart from the newest stored line |
| `app` | `ml-backend` | the backend's own Python and uvicorn logging, at INFO and above |
| `lifecycle` | each monitored service id | alarm episodes (logged once an episode has 8 alarming events, then again when it clears), quarantines, decisions, operator queries and answers, model transitions, demo injections |

The `q` filter is free text (case-insensitive) plus `service:`, `level:` and `source:` terms,
for example `checkpoint service:timescaledb level:error`. Repeating a key matches any of its
values. The browser applies the same grammar to lines arriving over the WebSocket, so a live tail
matches what a query would return.

Lines are stored in `service_logs` (a hypertable). The id is a hash of time, service and message, so
re-reading `docker logs --since` cannot create duplicates. Set `LOG_HTTP_ACCESS=true` to also log
every HTTP request, and `FOLLOW_CONTAINER_LOGS=false` if Docker isn't on the PATH.

## Persistence (TimescaleDB)

The schema lives in `infrastructure/local/init.sql`, and the backend also applies it on startup.
Tables:
- `metric_events` (hypertable: every 10th scored event per service plus every alarming one, kept
  6 hours; `PERSIST_EVERY` changes the sampling)
- `model_versions`
- `lifecycle_transitions`
- `lifecycle_decisions`
- `operator_queries`
- `change_events`
- `service_logs` (hypertable: the log stream above, kept 7 days)

```powershell
docker exec selfheal-demo-timescaledb-1 psql -U postgres -d selfheal -c "select * from lifecycle_decisions order by time desc limit 5"
docker exec selfheal-demo-redis-1 redis-cli XREVRANGE anomaly_events + - COUNT 3
```

## Tests

```powershell
uv run pytest      # in-memory fallbacks, two services on the demo's calm windows, no Docker needed
```
