Here's the full replacement. Copy the whole thing into services/decision-engine/README.md.

markdown

# Decision Engine — Component 2

Context-aware, dependency-driven decision engine for the Self-Healing
AI-Driven Failure Prediction and Automated Recovery Framework.

The service currently:

- Maintains a service dependency graph in memory and mirrors it to Neo4j Aura.
- Produces mock infrastructure, application, and anomaly telemetry.
  The mock source is temporary and will be replaced by Component 1.
- Keeps recent telemetry in a per-service in-memory ring buffer.
- Persists anomaly events in Neon Postgres.
- Captures telemetry snapshots **around** anomalies (T−5min … T+5min)
  in Tiger Cloud TimescaleDB using a **two-phase** strategy.
- Exposes REST APIs for the frontend and downstream components.

---

## Architecture

```text
                    Decision Engine
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Static topology ──► GraphStore ──► Graph REST API          │
│                        │                                    │
│                        └──────────────► Neo4j Aura          │
│                                                             │
│  Mock telemetry ──► telemetry puller (10s)                  │
│                  └─► in-memory ring buffer (13 min)         │
│                                                             │
│  Anomaly poller (5s) ──► for each unhealthy service:        │
│      1. INSERT anomaly → Neon (status = pending)            │
│      2. _capture_phase1() NOW                               │
│            slice [T−5min, T] from ring buffer               │
│            INSERT rows → Tiger Cloud                        │
│      3. schedule _capture_phase2 at T+5min                  │
│            slice [T, T+5min] from ring buffer               │
│            INSERT rows → Tiger Cloud                        │
│            UPDATE anomaly → status = captured               │
│                                                             │
│  REST APIs: graph, catalog, telemetry, history, evidence    │
└─────────────────────────────────────────────────────────────┘
```

---

## Cloud databases

| Purpose                  | Service                   | Data                                           |
| ------------------------ | ------------------------- | ---------------------------------------------- |
| Dependency graph         | Neo4j Aura                | `Service` nodes and `DEPENDS_ON` relationships |
| Anomaly events           | Neon Postgres             | Rows in `anomaly_events`                       |
| Infrastructure telemetry | Tiger Cloud (TimescaleDB) | Rows in `infra_snapshots`                      |
| Application telemetry    | Tiger Cloud (TimescaleDB) | Rows in `app_snapshots`                        |

Neo4j supports graph traversals such as dependency closure and blast-radius
analysis. Neon stores relational anomaly events. Tiger Cloud stores time-series
telemetry in Timescale hypertables.

---

## Snapshot strategy — two-phase capture

Telemetry is **not** written to TimescaleDB continuously. Instead:

1. A background job (`telemetry_puller`) samples each service every 10 s and
   pushes the sample into a per-service in-memory ring buffer. The buffer
   retains the last `RING_BUFFER_RETENTION_SEC` (default 800 s ≈ 13 min).

2. A second background job (`poll_anomalies`) runs every 5 s. For every
   service currently reported unhealthy by the telemetry source, it does:
    - **Save the anomaly** to Neon with `snapshot_status = 'pending'`.
      The ID is deterministic per (scenario, service), so re-polling does
      **not** create duplicates.

    - **Phase 1 — capture the "before" window immediately**
      Slice the ring buffer for `[T − SNAPSHOT_BEFORE_SEC, T]` and insert
      those samples into `infra_snapshots` and `app_snapshots`, tagged with
      the anomaly ID. This must run _now_: the data still exists in the
      buffer, but will be evicted within minutes.

    - **Phase 2 — capture the "after" window later**
      Schedule a one-shot job at `T + SNAPSHOT_AFTER_SEC`. When it fires,
      slice the ring buffer for `[T, T + SNAPSHOT_AFTER_SEC]`, insert those
      samples, and update the anomaly row to `snapshot_status = 'captured'`.

**Why two phases?** The `+5 min` half of the window does not exist at
detection time — you must wait. But by the time `+5 min` has elapsed, the
`−5 min` half would have been evicted from the ring buffer. Capturing the
"before" half immediately is the only way to preserve it.

Each snapshot row includes the anomaly ID. The schema associates rows by
convention and does not declare a database-enforced foreign key to Neon.

Example query — pull the full window for one anomaly:

```sql
SELECT *
FROM infra_snapshots
WHERE anomaly_id = 'ANM-auth_outage-auth-service'
ORDER BY time;
```

---

## Project layout

```text
services/decision-engine/
├── app/
│   ├── main.py                         # FastAPI app, lifecycle, debug endpoints
│   ├── config.py                       # .env settings and validation
│   ├── api/routes/
│   │   ├── graph.py                    # Graph endpoints
│   │   ├── health.py                   # Health endpoint
│   │   ├── mock_data.py                # Temporary mock telemetry and scenarios
│   │   ├── anomaly_evidence.py         # Anomaly evidence bundle
│   │   └── telemetry_history.py        # Snapshot history
│   ├── core/                           # Graph store, models, centrality, blast radius
│   ├── topology/sources/               # Static seed and future Kubernetes source
│   ├── persistence/                    # Neon, Timescale, Neo4j clients and DDL
│   └── ingestion/
│       ├── ring_buffer.py              # In-memory rolling buffer per service
│       ├── telemetry_puller.py         # Every 10 s → push into ring buffer
│       └── anomaly_sink.py             # Every 5 s → detect + two-phase capture
├── seeds/topology.yaml                 # Initial graph topology
├── tests/
├── .env                                # Local credentials; ignored by Git
├── pyproject.toml
└── README.md

app
 ┣ api
 ┃ ┣ routes
 ┃ ┃ ┣ __pycache__
 ┃ ┃ ┃ ┣ anomaly_evidence.cpython-314.pyc
 ┃ ┃ ┃ ┣ graph.cpython-314.pyc
 ┃ ┃ ┃ ┣ health.cpython-314.pyc
 ┃ ┃ ┃ ┣ mock_data.cpython-314.pyc
 ┃ ┃ ┃ ┗ telemetry_history.cpython-314.pyc
 ┃ ┃ ┣ anomaly_evidence.py
 ┃ ┃ ┣ graph.py
 ┃ ┃ ┣ health.py
 ┃ ┃ ┣ mock_data.py
 ┃ ┃ ┗ telemetry_history.py
 ┃ ┣ __pycache__
 ┃ ┃ ┗ __init__.cpython-314.pyc
 ┃ ┗ __init__.py
 ┣ core
 ┃ ┣ __pycache__
 ┃ ┃ ┣ blast_radius.cpython-314.pyc
 ┃ ┃ ┣ centrality.cpython-314.pyc
 ┃ ┃ ┣ graph_store.cpython-314.pyc
 ┃ ┃ ┗ models.cpython-314.pyc
 ┃ ┣ blast_radius.py
 ┃ ┣ centrality.py
 ┃ ┣ graph_store.py
 ┃ ┣ models.py
 ┃ ┗ root_cause.py
 ┣ events
 ┃ ┗ invalidation.py
 ┣ ingestion
 ┃ ┣ __pycache__
 ┃ ┃ ┣ anomaly_sink.cpython-314.pyc
 ┃ ┃ ┣ ring_buffer.cpython-314.pyc
 ┃ ┃ ┣ telemetry_puller.cpython-314.pyc
 ┃ ┃ ┗ __init__.cpython-314.pyc
 ┃ ┣ anomaly_sink.py
 ┃ ┣ ring_buffer.py
 ┃ ┣ telemetry_puller.py
 ┃ ┗ __init__.py
 ┣ persistence
 ┃ ┣ __pycache__
 ┃ ┃ ┣ migrate.cpython-314.pyc
 ┃ ┃ ┣ neo4j.cpython-314.pyc
 ┃ ┃ ┣ postgres.cpython-314.pyc
 ┃ ┃ ┣ schemas.cpython-314.pyc
 ┃ ┃ ┣ timescale.cpython-314.pyc
 ┃ ┃ ┗ __init__.cpython-314.pyc
 ┃ ┣ migrate.py
 ┃ ┣ neo4j.py
 ┃ ┣ postgres.py
 ┃ ┣ schemas.py
 ┃ ┣ timescale.py
 ┃ ┗ __init__.py
 ┣ topology
 ┃ ┣ sources
 ┃ ┃ ┣ __pycache__
 ┃ ┃ ┃ ┗ static_source.cpython-314.pyc
 ┃ ┃ ┣ kubernetes_source.py
 ┃ ┃ ┗ static_source.py
 ┃ ┣ __pycache__
 ┃ ┃ ┗ topology_updater.cpython-314.pyc
 ┃ ┣ k8s_watcher.py
 ┃ ┗ topology_updater.py
 ┣ __pycache__
 ┃ ┣ config.cpython-314.pyc
 ┃ ┗ main.cpython-314.pyc
 ┣ config.py
 ┗ main.py
```

---

## Configuration

Use Python 3.14 or later and `uv`. Create
`services/decision-engine/.env` with connection details from your database
providers:

```dotenv
# Neon Postgres: anomaly events
ANOMALY_DB_URL=postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require

# Tiger Cloud TimescaleDB: telemetry snapshots
TELEMETRY_DB_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require

# Neo4j Aura: dependency graph mirror
NEO4J_URI=neo4j+s://YOUR_INSTANCE.databases.neo4j.io
NEO4J_USER=YOUR_INSTANCE_ID
NEO4J_PASSWORD=YOUR_PASSWORD
NEO4J_DATABASE=YOUR_INSTANCE_ID

# Ingestion tuning
TELEMETRY_POLL_INTERVAL_SEC=10
ANOMALY_POLL_INTERVAL_SEC=5
RING_BUFFER_RETENTION_SEC=800
SNAPSHOT_BEFORE_SEC=300
SNAPSHOT_AFTER_SEC=300

# Mock telemetry source exposed by this service
TELEMETRY_SOURCE_URL=http://localhost:8000
```

The service fails startup if either Postgres URL, the Neo4j URI, or the
Neo4j password is missing. Neon and Tiger connections require SSL.
`.env` is ignored by Git; never commit database credentials.

**Important:** `RING_BUFFER_RETENTION_SEC` must be greater than
`SNAPSHOT_BEFORE_SEC + SNAPSHOT_AFTER_SEC`, otherwise the "before" half of
the window is evicted before it can be captured.

---

## Run locally

From the repository root:

```powershell
Set-Location services/decision-engine
uv sync
uv run uvicorn app.main:app --reload
```

Startup connects to Neon, Tiger Cloud, and Neo4j Aura, runs idempotent
schema migrations, loads `seeds/topology.yaml` into the in-memory graph,
mirrors the graph to Neo4j, and starts the ingestion jobs. A successful
startup ends with `Decision Engine startup complete`.

The API is available at `http://localhost:8000`. Interactive OpenAPI
documentation is at `http://localhost:8000/docs`.

---

## Test the pipeline

Run the service tests:

```powershell
Set-Location services/decision-engine
uv run pytest
```

Check the in-memory ring buffer:

```powershell
curl.exe http://localhost:8000/api/debug/buffer
```

Check persisted row counts:

```powershell
curl.exe http://localhost:8000/api/debug/db
```

Trigger a mock failure scenario:

```powershell
curl.exe -X POST http://localhost:8000/api/mock/scenario/auth_outage
```

Watch the backend log. Within ~5 s, you should see:

```text
New anomaly saved: ANM-auth_outage-auth-service on auth-service
Phase 1 for ANM-auth_outage-auth-service: 30 infra + 30 app points
Scheduled phase 2 for ANM-auth_outage-auth-service at 2026-10-12T19:14:17+00:00
```

Five minutes later, phase 2 fires for each anomaly:

```text
Phase 2 for ANM-auth_outage-auth-service: 30 infra + 30 app points
```

Then check the DB again — you should have ~5 anomalies and ~150 rows in
each snapshot table.

To stop the pipeline, reset the scenario:

```powershell
curl.exe -X POST http://localhost:8000/api/mock/scenario/all_healthy
```

---

## API reference

### Graph

| Method | Path                                   | Purpose                                          |
| ------ | -------------------------------------- | ------------------------------------------------ |
| GET    | `/api/graph/`                          | Full in-memory graph: nodes and edges            |
| GET    | `/api/graph/centrality`                | Centrality per service                           |
| GET    | `/api/graph/blast-radius/{service_id}` | Reverse-reachable set + blast-radius summary     |
| POST   | `/api/graph/refresh`                   | Topology refresh hook; implementation is pending |

### Mock catalog and telemetry

| Method | Path                           | Purpose                                                    |
| ------ | ------------------------------ | ---------------------------------------------------------- |
| GET    | `/api/services`                | Mock service catalog                                       |
| GET    | `/api/infra`                   | Infrastructure telemetry for all services                  |
| GET    | `/api/infra/{service_id}`      | Infrastructure telemetry for one service                   |
| GET    | `/api/app`                     | Application telemetry for all services                     |
| GET    | `/api/app/{service_id}`        | Application telemetry for one service                      |
| GET    | `/api/timeseries/{service_id}` | Mock time series (`metric`: `p99`, `rps`, or `error_rate`) |
| POST   | `/api/mock/scenario/{name}`    | Change the active mock failure scenario                    |
| GET    | `/api/mock/scenario`           | Current and available scenarios                            |

Available scenarios: `all_healthy`, `isolated_orders_slow`, `auth_outage`,
`database_degraded`, `payment_slowdown`, `cache_outage`, `kafka_lag`,
`edge_overload`.

### Persisted anomaly evidence and history

| Method | Path                                   | Purpose                                             |
| ------ | -------------------------------------- | --------------------------------------------------- |
| GET    | `/api/anomalies/recent`                | Recent anomalies                                    |
| GET    | `/api/anomalies/{anomaly_id}/evidence` | Neon anomaly row + associated infra/app snapshots   |
| POST   | `/api/anomalies/capture/{anomaly_id}`  | Force re-run of phase 1 + phase 2 (debug)           |
| GET    | `/api/history/{service_id}`            | Recent infra and app snapshot history for a service |
| GET    | `/api/history/infra/{anomaly_id}`      | Infra snapshots associated with an anomaly          |
| GET    | `/api/history/app/{anomaly_id}`        | App snapshots associated with an anomaly            |

### Health and diagnostics

| Method | Path                | Purpose                                    |
| ------ | ------------------- | ------------------------------------------ |
| GET    | `/health`           | Service health                             |
| GET    | `/api/debug/buffer` | Ring-buffer point counts                   |
| GET    | `/api/debug/db`     | Neon anomaly and Tiger snapshot row counts |

### Route disambiguation note

`mock_data.py` and `anomaly_evidence.py` both register
`GET /api/anomalies/recent`. `main.py` includes the mock router first, so
the mock route currently handles this path. The two must be disambiguated
in a follow-up: either rename the mock route (e.g. `/api/mock/anomalies`)
or drop it entirely once Component 1 replaces the mock source.

---

## View the cloud data

### Neon Postgres

Use the Neon Console's SQL Editor for quick queries, or connect with a
PostgreSQL client such as pgAdmin or DBeaver.

For pgAdmin: create a PostgreSQL server connection using the host, port,
database, username, and password from the Neon connection string. Set SSL
mode to **Require**. Then browse
`Databases → your database → Schemas → public → Tables → anomaly_events`
and choose **View/Edit Data → All Rows**.

### Tiger Cloud TimescaleDB

TimescaleDB speaks the PostgreSQL protocol, so the Tiger service can also
be opened with pgAdmin or DBeaver. Create a separate PostgreSQL connection
using the connection details from the Tiger Cloud console and require SSL.
The Tiger Cloud console also provides a SQL editor.

Useful queries:

```sql
-- Tables in the public schema
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;

-- Confirm the TimescaleDB extension
SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';

-- List hypertables
SELECT hypertable_name, num_dimensions FROM timescaledb_information.hypertables;

-- Snapshot row counts
SELECT COUNT(*) FROM infra_snapshots;
SELECT COUNT(*) FROM app_snapshots;

-- Recent infrastructure snapshots
SELECT anomaly_id, time, service_id, cpu_usage_pct, mem_pct, ready_pods
FROM infra_snapshots
ORDER BY time DESC
LIMIT 20;

-- All infrastructure samples for one anomaly
SELECT *
FROM infra_snapshots
WHERE anomaly_id = 'ANM-auth_outage-auth-service'
ORDER BY time;
```

### Neo4j Aura

Open the Neo4j Aura project and use its Query tool. The service mirrors
topology as `Service` nodes and `DEPENDS_ON` relationships.

```cypher
MATCH (s:Service) RETURN s LIMIT 50;

MATCH (a:Service)-[r:DEPENDS_ON]->(b:Service)
RETURN a.id AS caller, r.protocol AS protocol, b.id AS dependency
LIMIT 100;
```

---

## Storage schema summary

### Neon: `anomaly_events`

One row per unique anomaly ID. Columns: service identity, score, severity,
metric, actual/expected values, deviation, confidence, model metadata,
feature JSON, `detected_at`, plus snapshot bookkeeping:

- `snapshot_status` — `pending` / `captured` / `failed`
- `snapshot_from` — lower bound of the window (T − BEFORE)
- `snapshot_to` — upper bound of the window (T + AFTER)
- `captured_at` — when phase 2 completed

### Tiger Cloud: `infra_snapshots` and `app_snapshots`

Both are Timescale hypertables partitioned by `time`. Snapshot rows include
`anomaly_id` and `service_id`. The schema does not declare a relational
foreign key to Neon — the association is by convention.

### Neo4j Aura

```cypher
(:Service {id, name, namespace, criticality, health})
(:Service)-[:DEPENDS_ON {strength, protocol}]->(:Service)
```

---

## Design notes and future work

- **Two-phase capture** is essential: the "before" half of the window must
  be captured immediately or it gets evicted from the ring buffer; the
  "after" half must be captured after the configured delay.
- **Anomaly-triggered snapshots** retain evidence around failures without
  storing every telemetry sample permanently. At 15 services × 4 anomalies
  per day, this is ~140 rows/day per table versus ~130 k rows/day for
  continuous ingestion.
- **Deterministic anomaly IDs** (`ANM-{scenario}-{service_id}`) make the
  ingestion idempotent — re-polling does not create duplicates.
- The current telemetry and anomaly generator is mock code;
  **Component 1 will replace it** when ready.
- Kubernetes service discovery can replace the static topology source.
- The graph refresh endpoint, authentication, and persisted
  centrality/blast-radius caching remain future work.
- A frontend evidence view (see the `anomalies` feature in the frontend
  workspace) consumes the anomaly evidence endpoint.

---

## License

Academic research project, 4th Year Project, 2026.
🔑 Key Differences to Notice
1 — The README now explains the two-phase design
Before it said: "waits for the configured post-anomaly window, selects buffered samples from before and after detection" — vague.

Now it says exactly what happens in which order.

2 — Correct values
Before Now
T−30s to T+30s T−5min to T+5min
retention 120s 800s
"snapshot after T+30s" two phases: now + T+5min
3 — Added POST /api/anomalies/capture/{id}
That's the debug endpoint we added earlier.

4 — Added a warning about retention
RING_BUFFER_RETENTION_SEC must be greater than
SNAPSHOT_BEFORE_SEC + SNAPSHOT_AFTER_SEC

This is a gotcha — if you set retention too small, the before-window is gone by the time phase 1 runs. Worth documenting.

5 — Added a "Route disambiguation note"
The current README honestly flags the /api/anomalies/recent conflict between mock_data.py and anomaly_evidence.py.

🚦 How to Apply
Just copy the whole updated README into services/decision-engine/README.md.

Then:

powershell
cd services/decision-engine
git diff README.md # see what changed
git add README.md
git commit -m "docs: update README for two-phase snapshot design"
