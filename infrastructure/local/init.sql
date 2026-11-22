-- Schema for ml-backend (Doc1 §3 / Doc3 Phase 1, extended for the model lifecycle and tenancy).
-- Applied idempotently by services/ml-backend on every startup, so this file and
-- services/ml-backend/app/store.py must stay in step.
--
-- Tenancy (docs/adr/0015): every row belongs to one organization, `tenant_id`, which is part of
-- every key. 'default' is the tenant when authentication is off (the laptop demo).
--
-- TimescaleDB is optional (docs/adr/0016). Where the extension exists (the laptop stack, the
-- cluster) the two time series tables become hypertables with retention policies; on plain
-- PostgreSQL (Render's managed database) they stay ordinary tables and the backend deletes old
-- rows itself (store.PgStore.prune).

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb') THEN
        CREATE EXTENSION IF NOT EXISTS timescaledb;
    END IF;
END $$;

-- One row per scored telemetry event (Doc1 columns + what the lifecycle served).
CREATE TABLE IF NOT EXISTS metric_events (
    tenant_id       TEXT        NOT NULL DEFAULT 'default',
    time            TIMESTAMPTZ NOT NULL,
    service_id      TEXT        NOT NULL,
    anomaly_score   DOUBLE PRECISION,
    severity        TEXT,
    drift_detected  BOOLEAN,
    features        JSONB,
    alarm           BOOLEAN,
    threshold       DOUBLE PRECISION,
    model_version   INTEGER,
    phase           TEXT
);

-- Every model version the lifecycle registered (the MLflow registry mirror).
CREATE TABLE IF NOT EXISTS model_versions (
    tenant_id   TEXT        NOT NULL DEFAULT 'default',
    service_id  TEXT        NOT NULL,
    version     INTEGER     NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    status      TEXT        NOT NULL,
    threshold   DOUBLE PRECISION,
    kind        TEXT,
    verdict     TEXT,
    reason      TEXT,
    tags        JSONB,
    PRIMARY KEY (tenant_id, service_id, version)
);

-- Append-only audit trail of every registry transition (proposal FR4).
CREATE TABLE IF NOT EXISTS lifecycle_transitions (
    tenant_id     TEXT        NOT NULL DEFAULT 'default',
    service_id    TEXT        NOT NULL,
    seq           INTEGER     NOT NULL,
    time          TIMESTAMPTZ NOT NULL DEFAULT now(),
    transition    TEXT        NOT NULL,
    from_version  INTEGER,
    to_version    INTEGER,
    reason        TEXT,
    evidence      JSONB,
    PRIMARY KEY (tenant_id, service_id, seq)
);

-- Every lifecycle decision with its attribution evidence.
CREATE TABLE IF NOT EXISTS lifecycle_decisions (
    tenant_id   TEXT        NOT NULL DEFAULT 'default',
    time        TIMESTAMPTZ NOT NULL DEFAULT now(),
    service_id  TEXT        NOT NULL,
    step        INTEGER,
    action      TEXT,
    verdict     TEXT,
    trigger     TEXT,
    reason      TEXT,
    evidence    JSONB,
    query_id    TEXT
);

-- Operator-in-the-loop queries and their answers.
CREATE TABLE IF NOT EXISTS operator_queries (
    tenant_id    TEXT        NOT NULL DEFAULT 'default',
    query_id     TEXT        NOT NULL,
    service_id   TEXT        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    status       TEXT        NOT NULL,
    answer       TEXT,
    operator     TEXT,
    answered_at  TIMESTAMPTZ,
    reason       TEXT,
    evidence     JSONB,
    PRIMARY KEY (tenant_id, query_id)
);

-- Exogenous changes (deployments, config) the lifecycle was told about.
CREATE TABLE IF NOT EXISTS change_events (
    tenant_id   TEXT        NOT NULL DEFAULT 'default',
    time        TIMESTAMPTZ NOT NULL DEFAULT now(),
    service_id  TEXT        NOT NULL,
    kind        TEXT        NOT NULL,
    detail      JSONB
);

-- Log stream for the Logs page: container output (TimescaleDB, Redis), the backend's own logging,
-- and one line per notable lifecycle event of each monitored service. `id` is a content hash, so
-- replaying `docker logs --since` after a restart cannot create duplicates.
CREATE TABLE IF NOT EXISTS service_logs (
    tenant_id   TEXT        NOT NULL DEFAULT 'default',
    time        TIMESTAMPTZ NOT NULL,
    id          TEXT        NOT NULL,
    service     TEXT        NOT NULL,
    service_id  TEXT,
    source      TEXT        NOT NULL,
    level       TEXT        NOT NULL,
    message     TEXT        NOT NULL,
    attrs       JSONB,
    PRIMARY KEY (tenant_id, id, time)
);

-- One lifecycle checkpoint per monitored service (docs/adr/0006): the whole registry, thresholds,
-- re-baselining state and operator queries, so a restarted backend resumes instead of re-warming.
-- `source` is what the service was built from (SMD machine or namespace/deployment); a checkpoint
-- is only restored onto the same source.
CREATE TABLE IF NOT EXISTS model_checkpoints (
    tenant_id           TEXT        NOT NULL DEFAULT 'default',
    service_id          TEXT        NOT NULL,
    source              TEXT        NOT NULL,
    saved_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    step                BIGINT,
    production_version  INTEGER,
    blob                BYTEA       NOT NULL,
    PRIMARY KEY (tenant_id, service_id)
);

-- Migrate databases created before tenancy: add the column, then put it into each key.
DO $$
DECLARE
    t TEXT;
    keys JSONB := '{"model_versions": "tenant_id, service_id, version",
                    "lifecycle_transitions": "tenant_id, service_id, seq",
                    "operator_queries": "tenant_id, query_id",
                    "service_logs": "tenant_id, id, time",
                    "model_checkpoints": "tenant_id, service_id"}';
    pk TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['metric_events', 'model_versions', 'lifecycle_transitions',
                             'lifecycle_decisions', 'operator_queries', 'change_events',
                             'service_logs', 'model_checkpoints'] LOOP
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT %L',
                       t, 'default');
    END LOOP;
    FOR t IN SELECT jsonb_object_keys(keys) LOOP
        SELECT c.conname INTO pk FROM pg_constraint c
         WHERE c.conrelid = t::regclass AND c.contype = 'p';
        IF pk IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM pg_constraint c JOIN pg_attribute a
              ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
             WHERE c.conname = pk AND c.conrelid = t::regclass AND a.attname = 'tenant_id') THEN
            EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', t, pk);
            EXECUTE format('ALTER TABLE %I ADD PRIMARY KEY (%s)', t, keys ->> t);
        END IF;
    END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS metric_events_tenant_service_time ON metric_events (tenant_id, service_id, time DESC);
CREATE INDEX IF NOT EXISTS lifecycle_decisions_tenant_service_time ON lifecycle_decisions (tenant_id, service_id, time DESC);
CREATE INDEX IF NOT EXISTS service_logs_tenant_service_time ON service_logs (tenant_id, service, time DESC);
CREATE INDEX IF NOT EXISTS service_logs_tenant_level_time ON service_logs (tenant_id, level, time DESC);
DROP INDEX IF EXISTS metric_events_service_time;
DROP INDEX IF EXISTS lifecycle_decisions_service_time;
DROP INDEX IF EXISTS service_logs_service_time;
DROP INDEX IF EXISTS service_logs_level_time;

-- Hypertables and retention where TimescaleDB is installed. The demo replays 60x faster than real
-- time, so unbounded history would grow ~1 GB an hour; chunks are an hour wide so retention can
-- actually drop them (it only drops whole chunks).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('metric_events', 'time', chunk_time_interval => INTERVAL '1 hour',
                                  if_not_exists => TRUE, migrate_data => TRUE);
        PERFORM set_chunk_time_interval('metric_events', INTERVAL '1 hour');
        PERFORM add_retention_policy('metric_events', INTERVAL '6 hours', if_not_exists => TRUE);
        PERFORM create_hypertable('service_logs', 'time', chunk_time_interval => INTERVAL '1 day',
                                  if_not_exists => TRUE, migrate_data => TRUE);
        PERFORM add_retention_policy('service_logs', INTERVAL '7 days', if_not_exists => TRUE);
    END IF;
END $$;
