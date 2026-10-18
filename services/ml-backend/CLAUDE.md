# services/ml-backend

FastAPI service owning telemetry ingestion, the streaming ML engine and the model registry client
(Doc1 §2). Right now it runs the Component 1 + 2 demo: a replay of real SMD telemetry through
`ml-pipeline`'s `DynamicModelManager` (smoothed PCA + POT detector, CADAL lifecycle with operator
queries), persisted to TimescaleDB and streamed over Redis and a WebSocket. See `README.md` for the
runbook and the full REST/WebSocket contract.

**Tech**: Python 3.11 (uv), FastAPI, asyncpg, redis.asyncio, river 0.25.0 (pinned: 0.26 removed
`river.anomaly.base`, which ml-pipeline uses).

**Layout**
- `app/core/pipeline_path.py` imports ml-pipeline from source (`ML_PIPELINE_DIR`). Never copy
  ML code into this service; change it in ml-pipeline.
- `app/fleet.py`: one `DynamicModelManager` per demo service, plus the demo injections. Registry
  and lifecycle events go into a per-service `Outbox`.
- `app/runtime.py`: the replay loop. It drains each outbox into the store and the bus.
- `app/store.py`: `PgStore` (asyncpg), with `MemoryStore` as the fallback.
- `app/bus.py`: Redis Pub/Sub + Stream, with an in-process fallback.
- `app/api/`: `routes.py` (REST), `websocket.py`, and `views.py` (JSON shaped like the frontend's
  types).

**Gotchas**
- The demo service to SMD entity mapping in `fleet.py` was picked by rehearsing all 28 machines.
  Entities like machine-1-1, 2-6 and 3-11 hold on a deployment because they are noisy early in
  their test split. Re-rehearse before changing the mapping.
- The demo pacing (`DEMO_SAMPLES_PER_DAY`) is not the evaluated configuration; don't quote demo
  timings as results.
- Tests set `START_REPLAY=false` and `USE_BACKING_SERVICES=false`, and step the fleet through
  `client.portal.call(runtime.step_all)`.

Severity thresholds (shared with `services/decision-engine`): `< 0.5` watch, `0.5-0.7` warn,
`0.7-0.85` degrade, `> 0.85` critical. The normalized score maps each version's calibrated
threshold to 0.5.
