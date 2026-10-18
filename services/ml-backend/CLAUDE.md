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
- `app/logs.py`: the Logs page stream (container `docker logs -f` threads, Python logging, one line per
  lifecycle event). The hub only appends to a deque from any thread; the replay loop flushes it into
  `service_logs` and the bus. Store failures for logs log at DEBUG on purpose: a warning would itself
  become a log line and feed back.
- `app/api/`: `routes.py` (REST), `websocket.py`, and `views.py` (JSON shaped like the frontend's
  types).

**Gotchas**
- Each service replays a calm, label-free 6000-row window of its SMD test split, ping-ponged so
  there is no wrap-around jump. The windows and the service mapping in `fleet.py` were chosen by
  rehearsing the scenarios offline, including each model's alarm rate after the decision. Replaying
  whole test splits (`REPLAY_WINDOW_ROWS=0`) brings in the real labelled anomalies, so every service
  starts drifting and asking within minutes. Re-rehearse before changing the mapping.
- `DEMO_SAMPLES_PER_DAY=1440` is the evaluated lifecycle; only the replay speed (60 eps) is demo
  specific. Smaller values shorten the quarantine. At 960 the PCA challenger is fitted on 480 rows of
  38 metrics, which pushes the learnable floor to ~1.0, and bad challengers get promoted. Don't quote
  demo timings as results.
- The replay loop runs on time credit (wake every 50 ms, step as often as earned). Sleeping once per
  event capped it at ~33 eps on Windows.
- Tests set `START_REPLAY=false` and `USE_BACKING_SERVICES=false`, and step the fleet through
  `client.portal.call(runtime.step_all)`.

Severity thresholds (shared with `services/decision-engine`): `< 0.5` watch, `0.5-0.7` warn,
`0.7-0.85` degrade, `> 0.85` critical. The normalized score maps each version's calibrated
threshold to 0.5.
