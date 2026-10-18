-- Schema for the ml-backend demo (Doc1 §3 / Doc3 Phase 1, extended for the model lifecycle).
-- Also applied idempotently by services/ml-backend on startup, so this file and
-- services/ml-backend/app/store.py must stay in step.
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- One row per scored telemetry event (Doc1 columns + what the lifecycle served).
CREATE TABLE IF NOT EXISTS metric_events (
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
SELECT create_hypertable('metric_events', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS metric_events_service_time ON metric_events (service_id, time DESC);

-- Every model version the lifecycle registered (the MLflow registry mirror).
CREATE TABLE IF NOT EXISTS model_versions (
    service_id  TEXT        NOT NULL,
    version     INTEGER     NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    status      TEXT        NOT NULL,
    threshold   DOUBLE PRECISION,
    kind        TEXT,
    verdict     TEXT,
    reason      TEXT,
    tags        JSONB,
    PRIMARY KEY (service_id, version)
);

-- Append-only audit trail of every registry transition (proposal FR4).
CREATE TABLE IF NOT EXISTS lifecycle_transitions (
    service_id    TEXT        NOT NULL,
    seq           INTEGER     NOT NULL,
    time          TIMESTAMPTZ NOT NULL DEFAULT now(),
    transition    TEXT        NOT NULL,
    from_version  INTEGER,
    to_version    INTEGER,
    reason        TEXT,
    evidence      JSONB,
    PRIMARY KEY (service_id, seq)
);

-- Every lifecycle decision with its attribution evidence.
CREATE TABLE IF NOT EXISTS lifecycle_decisions (
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
CREATE INDEX IF NOT EXISTS lifecycle_decisions_service_time ON lifecycle_decisions (service_id, time DESC);

-- Operator-in-the-loop queries and their answers.
CREATE TABLE IF NOT EXISTS operator_queries (
    query_id     TEXT PRIMARY KEY,
    service_id   TEXT        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    status       TEXT        NOT NULL,
    answer       TEXT,
    operator     TEXT,
    answered_at  TIMESTAMPTZ,
    reason       TEXT,
    evidence     JSONB
);

-- Exogenous changes (deployments, config) the lifecycle was told about.
CREATE TABLE IF NOT EXISTS change_events (
    time        TIMESTAMPTZ NOT NULL DEFAULT now(),
    service_id  TEXT        NOT NULL,
    kind        TEXT        NOT NULL,
    detail      JSONB
);
