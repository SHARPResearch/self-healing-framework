---
name: local-dev-stack
description: Start or stop the local development dependencies for self-healing-framework (Redis, TimescaleDB+pgvector, MLflow tracking server) as specified in docs/Doc3_Execution_Guide.md Phase 0-1. Use when the user wants to run services locally, needs Redis/TimescaleDB/MLflow running, or asks to set up/tear down the local dev stack.
---

# Local dev stack

Brings up the three local dependencies the FastAPI `ml-backend` and .NET `decision-engine`
services need during local development. Source: `docs/Doc3_Execution_Guide.md` Phase 0-1.

## Start

```bash
# Redis (Streams + Pub/Sub)
docker run -d --name redis-dev \
  -p 6379:6379 \
  redis:7-alpine \
  redis-server --appendonly yes

# TimescaleDB + pgvector
docker run -d --name timescaledb-dev \
  -e POSTGRES_PASSWORD=selfheal \
  -e POSTGRES_DB=selfheal \
  -p 5432:5432 \
  timescale/timescaledb-ha:pg16

# Wait ~10s for Postgres to accept connections, then initialise schema:
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

# MLflow tracking server (sqlite backend — file-store backend is unsupported on mlflow>=3)
mlflow server \
  --backend-store-uri sqlite:///mlflow.db \
  --default-artifact-root ./mlflow-artifacts \
  --host 0.0.0.0 \
  --port 5001 &
```

Verify: `docker ps` shows `redis-dev` and `timescaledb-dev` running; http://localhost:5001 loads
the MLflow UI.

## Stop

```bash
docker stop redis-dev timescaledb-dev
docker rm redis-dev timescaledb-dev
# Stop the mlflow server process (it was backgrounded with &)
pkill -f "mlflow server" || true
```

## Notes

- These containers are named `-dev` and are throwaway — `docker rm` them freely, no volumes are
  mounted so data does not persist across restarts (fine for local dev; do not rely on this for
  anything you need to keep).
- Requires Docker Desktop running. If unavailable, `helm`/`kubectl`/Minikube-based setup is
  documented in Phase 0 of `docs/Doc3_Execution_Guide.md` instead.
