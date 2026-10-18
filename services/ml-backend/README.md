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
uv run uvicorn app.main:app --port 8000

# 3. Frontend (second terminal)
cd frontend
pnpm dev        # http://localhost:5173, proxies /api and /ws to :8000
```

`GET http://localhost:8000/api/health` should report `"db": true, "redis": true`. If Docker isn't
running, the backend still starts: it falls back to an in-memory store and an in-process bus and
logs a warning, so the UI keeps working.

## What runs

Six demo services, each replaying one SMD machine's test split after warming up on its train split:

| Service | SMD entity |
|---|---|
| service-a-auth | machine-1-6 |
| service-b-orders | machine-1-3 |
| service-c-inventory | machine-2-2 |
| service-d-shipping | machine-2-5 |
| service-e-payments | machine-3-3 |
| service-f-search | machine-2-9 |

These entities were chosen by rehearsing all 28 SMD machines offline. On each of them all three
demo injections lead to the intended lifecycle outcome, and none raise alarms before an injection.

**Demo pacing:** one lifecycle "day" is `DEMO_SAMPLES_PER_DAY=960` events, and the replay runs at
`REPLAY_EVENTS_PER_SEC=40`, so a quarantine closes in about 24 s. This is presentation pacing, not
the evaluated configuration (see `ml-pipeline/RESULTS_COMPONENT2.md`).

Demo injections (`POST /api/demo/{service}/{kind}`):

| kind | What it does | Expected outcome |
|---|---|---|
| `deploy` | Persistent level shift on some metrics, plus a deployment change event | `concept_drift` → **promote** (learned) |
| `silent_change` | Persistent level and spread change with no change event | `ambiguous` → **ask** the operator |
| `incident` | 20 s spike on ~1/8 of the metrics | `incident` → **hold**, or `no_change` → **resume**; never learned |

## Configuration (env or `.env`)

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql://postgres:selfheal@localhost:5433/selfheal` |
| `REDIS_URL` | `redis://localhost:6380` |
| `DETECTOR` / `THRESHOLD_METHOD` | `pca_s5` / `pot` |
| `REPLAY_EVENTS_PER_SEC` | `40` |
| `DEMO_SAMPLES_PER_DAY` | `960` |
| `QUERY_TTL_EVENTS` | `12000` (~5 min to answer a query on stage) |
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
| POST | `/models/{id}/rollback` | body `{version?, operator}`; rolls back to the previous production version by default |
| POST | `/models/{id}/validity-check` | opens an operator-triggered quarantine |
| GET | `/lifecycle/decisions?service_id=&limit=` | the decision log, newest first |
| GET | `/queries?status=open` | operator queries |
| POST | `/queries/{id}/answer` | body `{answer: "new_normal" \| "incident", operator}` |
| GET | `/demo/state` | per-service step and active injections |
| POST | `/demo/{id}/{deploy\|silent_change\|incident}` | injects a scenario |
| POST | `/demo/speed` | body `{eventsPerSec?, paused?}` |
| POST | `/demo/reset` | rebuilds the fleet from scratch |

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

Every message is also published to Redis Pub/Sub `ws:anomaly_broadcast` and appended to the Redis
Stream `anomaly_events` (maxlen 20000), where the Decision Engine will consume it.

## Persistence (TimescaleDB)

The schema lives in `infrastructure/local/init.sql`, and the backend also applies it on startup.
Tables:
- `metric_events` (hypertable: every scored event)
- `model_versions`
- `lifecycle_transitions`
- `lifecycle_decisions`
- `operator_queries`
- `change_events`

```powershell
docker exec selfheal-demo-timescaledb-1 psql -U postgres -d selfheal -c "select * from lifecycle_decisions order by time desc limit 5"
docker exec selfheal-demo-redis-1 redis-cli XREVRANGE anomaly_events + - COUNT 3
```

## Tests

```powershell
uv run pytest      # in-memory fallbacks, one service on machine-1-6, no Docker needed
```
