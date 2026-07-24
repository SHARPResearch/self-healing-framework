# services/ml-backend

FastAPI service owning telemetry ingestion, the streaming ML engine, and the MLflow model
registry client (Doc1 §2: "Telemetry Ingestion API", "Streaming ML Engine", "Model Registry").

**Tech**: Python 3.11, FastAPI, `river` (Half-Space Trees + ADWIN), MLflow, Redis Streams/Pub-Sub,
TimescaleDB + pgvector (via asyncpg/SQLAlchemy).

**Status**: scaffold only (`.gitkeep`, `Makefile`, `docker-compose.yml`, `requirements.txt`). No
`app/` package exists yet except the `app/ml/` placeholder, which is where the individual
"Component 1/2/4" research pieces (anomaly detection, dynamic model updating, adaptive learning)
land as real modules — not as separate services.

**Build next** (`docs/Doc3_Execution_Guide.md` Phase 1 & 3, in order):
1. `uv init --python 3.11` + `uv add fastapi "uvicorn[standard]" redis river mlflow pydantic-settings prometheus-client asyncpg pgvector "sqlalchemy[asyncio]"`
2. `app/main.py` — FastAPI app factory + `lifespan()` initialising Redis + HST model registry
3. `app/config.py` — Pydantic `Settings` reading `REDIS_URL`, `MLFLOW_TRACKING_URI`, `PROMETHEUS_URL`
4. `app/core/{feature_extractor,ring_buffer,redis_client}.py`
5. `app/ml/{hst_model,adwin_detector,model_manager}.py` — see `docs/Component_1_2_Technical_Guide.md`
   for the reference implementation (currently standalone at `ml-pipeline/`)
6. `app/api/routes/{ingest,predict,models,health}.py`, `app/api/websocket.py`
7. `tests/unit/` + `tests/integration/`

Severity thresholds (shared with `services/decision-engine`): `< 0.5` watch, `0.5-0.7` warn,
`0.7-0.85` degrade, `> 0.85` critical.
