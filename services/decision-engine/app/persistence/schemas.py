"""
All DDL in one place. Run once on startup (idempotent).
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS anomaly_events (
    id              TEXT PRIMARY KEY,
    service_id      TEXT NOT NULL,
    service_name    TEXT,
    team            TEXT,
    layer           TEXT,
    anomaly_score   REAL NOT NULL,
    severity        TEXT NOT NULL,
    metric          TEXT,
    actual_value    DOUBLE PRECISION,
    expected_value  DOUBLE PRECISION,
    deviation_sigma REAL,
    confidence      REAL,
    model_version   TEXT,
    features        JSONB,
    detected_at     TIMESTAMPTZ NOT NULL,
    snapshot_status TEXT NOT NULL DEFAULT 'pending',
    snapshot_from   TIMESTAMPTZ,
    snapshot_to     TIMESTAMPTZ,
    captured_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_anom_service_time
    ON anomaly_events (service_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anom_status
    ON anomaly_events (snapshot_status)
    WHERE snapshot_status = 'pending';
"""


TIMESCALE_SCHEMA = """
-- Infra snapshots ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS infra_snapshots (
    anomaly_id      TEXT NOT NULL,
    time            TIMESTAMPTZ NOT NULL,
    service_id      TEXT NOT NULL,

    -- identity
    service_name    TEXT,
    layer           TEXT,
    team            TEXT,
    runtime         TEXT,
    version         TEXT,
    region          TEXT,
    node_pool       TEXT,
    node            TEXT,
    container_image TEXT,
    uptime_seconds  INTEGER,

    -- pods
    pod_count       INTEGER,
    ready_pods      INTEGER,
    restarts_last_5m INTEGER,

    -- cpu
    cpu_usage_pct   REAL,
    cpu_cores_used  REAL,
    cpu_throttled_pct REAL,

    -- memory
    mem_used_mb     INTEGER,
    mem_limit_mb    INTEGER,
    mem_pct         REAL,
    mem_oom_kills   INTEGER,

    -- network
    net_rx_kbps     INTEGER,
    net_tx_kbps     INTEGER,

    -- disk
    disk_read_iops  INTEGER,
    disk_write_iops INTEGER,
    disk_used_pct   REAL,

    -- gc
    gc_pause_p95_ms REAL,
    gc_collections  INTEGER,

    -- raw payload for future-proofing
    raw             JSONB,
    UNIQUE (anomaly_id, time)
);
SELECT create_hypertable('infra_snapshots', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_infra_anomaly
    ON infra_snapshots (anomaly_id, time);


-- App snapshots ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS app_snapshots (
    anomaly_id      TEXT NOT NULL,
    time            TIMESTAMPTZ NOT NULL,
    service_id      TEXT NOT NULL,
    
    service_name    TEXT,
    layer           TEXT,
    team            TEXT,

    rps             REAL,
    throughput_bps  INTEGER,

    latency_p50     REAL,
    latency_p90     REAL,
    latency_p95     REAL,
    latency_p99     REAL,
    latency_p999    REAL,
    latency_max     REAL,

    error_rate      REAL,
    error_budget_pct REAL,

    status_2xx      INTEGER,
    status_3xx      INTEGER,
    status_4xx      INTEGER,
    status_5xx      INTEGER,

    active_conns    INTEGER,
    queue_depth     INTEGER,
    queue_lag_ms    REAL,

    db_p95_ms       REAL,
    db_pool_used    INTEGER,
    db_pool_max     INTEGER,

    cache_hit_rate  REAL,
    cache_evictions INTEGER,

    saturation_pct  REAL,

    raw             JSONB,
    UNIQUE (anomaly_id, time)
);
SELECT create_hypertable('app_snapshots', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_app_anomaly
    ON app_snapshots (anomaly_id, time);
"""