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

| Service | SMD entity, window start | Best scenario to show |
|---|---|---|
| service-a-auth | machine-2-9, row 0 | deploy → promote |
| service-b-orders | machine-3-10, row 15250 | deploy → promote; a silent change is repaired by re-baselining |
| service-c-inventory | machine-1-2, row 9250 | silent change → ask the operator |
| service-d-shipping | machine-2-8, row 0 | incident → resume (a silent change asks only early in the replay) |
| service-e-payments | machine-2-2, row 0 | incident → resume |
| service-f-search | machine-1-5, row 0 | incident → resume (sometimes hold or ask) |

How the windows were chosen:
- Each one is the label-free stretch of its machine's test split where the warm-up model alarms at
  about its POT target (0.1% to 3%). A service therefore stays calm until the presenter injects
  something.
- The mapping comes from rehearsing every candidate offline. Each scenario was run to its decision,
  and the model's alarm rate was then checked over the next two days of data. After every promotion
  in the table it stayed between 0% and 1.5%. The scenarios were also injected at five different
  points of the replay: deploys promoted every time on Auth, Orders and Inventory, a silent change on
  Inventory asked 4 times out of 5, and an incident on Payments resumed every time.
- Other scenarios still run on every service and show real behaviour. For example, a deploy on
  Payments is held, because some of its metrics keep trending ("still moving") and CADAL won't learn
  a regime that hasn't settled.

**Pacing:** `DEMO_SAMPLES_PER_DAY=1440` is SMD's own one sample a minute, so the lifecycle runs with
the evaluated lengths. The replay runs at 60 events/s, 60x real time, so a one-day quarantine closes
in about 24 s on stage.

Demo injections (`POST /api/demo/{service}/{kind}`):

| kind | What it does | Expected outcome |
|---|---|---|
| `deploy` | Persistent level shift on some metrics, plus a deployment change event | `concept_drift` → **promote** (learned) |
| `silent_change` | Persistent level and spread change with no change event | `ambiguous` → **ask** the operator |
| `incident` | Spike on ~1/8 of the metrics for a fifth of a day (~5 s) | `no_change` → **resume** or `incident` → **hold**; never learned |

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
uv run pytest      # in-memory fallbacks, two services on the demo's calm windows, no Docker needed
```
