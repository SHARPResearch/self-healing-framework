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


# ─────────────────────────────────────────────────────────────────────
# BATCH 1 — RULES (Component 2 Rule Engine)
# ─────────────────────────────────────────────────────────────────────
RULES_DDL = """
CREATE TABLE IF NOT EXISTS rules (
    id             TEXT PRIMARY KEY,
    version        INT NOT NULL DEFAULT 1,
    priority       INT NOT NULL DEFAULT 100,
    description    TEXT NOT NULL DEFAULT '',
    enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    applies_to     JSONB NOT NULL,
    when_condition JSONB NOT NULL,
    then_action    JSONB NOT NULL,
    guardrails     JSONB NOT NULL,
    tags           JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rules_enabled_priority
    ON rules (enabled, priority DESC);
"""

# ─────────────────────────────────────────────────────────────────────
# BATCH 2 — HYBRID RULE MANAGEMENT
#   * ownership / lifecycle columns on `rules`
#   * rule_audit — every write to a rule leaves a trace
# All statements are idempotent (ADD COLUMN IF NOT EXISTS / CREATE ... IF
# NOT EXISTS) so this is safe to run on every boot against an existing DB.
# ─────────────────────────────────────────────────────────────────────
RULES_HYBRID_DDL = """
ALTER TABLE rules ADD COLUMN IF NOT EXISTS is_default     BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE rules ADD COLUMN IF NOT EXISTS is_template    BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE rules ADD COLUMN IF NOT EXISTS created_by     TEXT NOT NULL DEFAULT 'system';
ALTER TABLE rules ADD COLUMN IF NOT EXISTS owner_org_id   TEXT;
ALTER TABLE rules ADD COLUMN IF NOT EXISTS status         TEXT NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE rules ADD COLUMN IF NOT EXISTS parent_rule_id TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'rules_status_check'
    ) THEN
        ALTER TABLE rules ADD CONSTRAINT rules_status_check
            CHECK (status IN ('DRAFT', 'ACTIVE', 'ARCHIVED'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'rules_parent_rule_fk'
    ) THEN
        ALTER TABLE rules ADD CONSTRAINT rules_parent_rule_fk
            FOREIGN KEY (parent_rule_id) REFERENCES rules(id) ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_rules_type
    ON rules (is_template, is_default, status, priority DESC);

-- Backfill: rules that predate the hybrid columns (created_by defaults to
-- 'system' for every pre-existing row) are the shipped defaults and must be
-- flagged as such. Without this they read as user rules and become deletable.
-- Idempotent: re-running only touches rows still at is_default = FALSE, and
-- never promotes a template.
UPDATE rules
   SET is_default = TRUE
 WHERE created_by = 'system'
   AND is_template = FALSE
   AND is_default = FALSE;
"""


RULE_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS rule_audit (
    id         BIGSERIAL PRIMARY KEY,
    rule_id    TEXT NOT NULL,
    action     TEXT NOT NULL CHECK (action IN ('CREATE','UPDATE','DELETE','TOGGLE','RELOAD')),
    actor      TEXT NOT NULL DEFAULT 'unknown',
    diff       JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rule_audit_rule
    ON rule_audit (rule_id, created_at DESC);
"""


# ─────────────────────────────────────────────────────────────────────
# BATCH 1 — Placeholders for later batches (schemas created now,
#           code that uses them lands in Batch 2/3/4).
# ─────────────────────────────────────────────────────────────────────
DECISION_LOG_DDL = """
CREATE TABLE IF NOT EXISTS decision_log (
    id                TEXT PRIMARY KEY,           -- DEC-{ulid}
    anomaly_id        TEXT NOT NULL,
    service_id        TEXT NOT NULL,
    rule_id           TEXT,
    rule_version      INT,

    action            TEXT NOT NULL,
    action_params     JSONB NOT NULL DEFAULT '{}'::jsonb,

    detection_conf    DOUBLE PRECISION NOT NULL DEFAULT 0,
    rule_conf         DOUBLE PRECISION NOT NULL DEFAULT 0,
    final_conf        DOUBLE PRECISION NOT NULL DEFAULT 0,

    base_risk         TEXT,
    blast_factor      DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    centrality        DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    effective_severity DOUBLE PRECISION NOT NULL DEFAULT 0,

    policy_outcome    TEXT NOT NULL,             -- AUTO_EXECUTE / SHADOW_MODE / HUMAN_LOOP / BLOCK
    policy_reason     TEXT,

    context           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_decision_log_anomaly  ON decision_log (anomaly_id);
CREATE INDEX IF NOT EXISTS idx_decision_log_service  ON decision_log (service_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decision_log_outcome  ON decision_log (policy_outcome, created_at DESC);
"""


SHADOW_RECORDS_DDL = """
CREATE TABLE IF NOT EXISTS shadow_records (
    id                 TEXT PRIMARY KEY,          -- SHD-{ulid}
    decision_id        TEXT NOT NULL,             -- FK by convention → decision_log.id
    anomaly_id         TEXT NOT NULL,
    service_id         TEXT NOT NULL,

    candidate_action   TEXT NOT NULL,
    confidence         DOUBLE PRECISION NOT NULL,
    risk               TEXT NOT NULL,

    simulated_outcome  JSONB NOT NULL DEFAULT '{}'::jsonb,
    actual_outcome     JSONB,
    verdict            TEXT,                      -- ACTION_WOULD_HAVE_HELPED / UNNECESSARY / HARMFUL / UNKNOWN
    learning           TEXT,

    observed_at        TIMESTAMPTZ,               -- when the actual outcome was observed
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_shadow_decision ON shadow_records (decision_id);
CREATE INDEX IF NOT EXISTS idx_shadow_verdict  ON shadow_records (verdict);
"""


ESCALATIONS_DDL = """
CREATE TABLE IF NOT EXISTS escalations (
    id              TEXT PRIMARY KEY,             -- ESC-{ulid}
    decision_id     TEXT NOT NULL,
    anomaly_id      TEXT NOT NULL,
    service_id      TEXT NOT NULL,

    status          TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING / AWAITING_HUMAN / RESOLVED / FAILED
    attempt         INT NOT NULL DEFAULT 0,           -- 0 → not sent; 1,2,3 → attempts
    max_attempts    INT NOT NULL DEFAULT 3,

    notifications   JSONB NOT NULL DEFAULT '[]'::jsonb, -- [{attempt, sent_at, message_id}]
    response        JSONB,                              -- {decision: approve|reject, by, at, note}
    failure_report  TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations (status, created_at DESC);
"""


ACTION_HISTORY_DDL = """
-- Used by Validation Layer: "has this action failed N times recently?"
CREATE TABLE IF NOT EXISTS action_history (
    id            BIGSERIAL PRIMARY KEY,
    decision_id   TEXT NOT NULL,
    service_id    TEXT NOT NULL,
    action        TEXT NOT NULL,
    outcome       TEXT NOT NULL,               -- SUCCESS / FAILED / NEUTRAL / UNKNOWN
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_action_history_lookup
    ON action_history (service_id, action, occurred_at DESC);
"""


IN_FLIGHT_ACTIONS_DDL = """
-- Used by Validation Layer: conflict detection.
CREATE TABLE IF NOT EXISTS in_flight_actions (
    decision_id   TEXT PRIMARY KEY,
    service_id    TEXT NOT NULL,
    action        TEXT NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMPTZ NOT NULL              -- guardrail.cooldown_seconds after started_at
);
CREATE INDEX IF NOT EXISTS idx_in_flight_service
    ON in_flight_actions (service_id, expires_at DESC);
"""

# ─────────────────────────────────────────────────────────────────────
# INCIDENT LIFECYCLE — one row per service, tracks current incident
# ─────────────────────────────────────────────────────────────────────
INCIDENT_STATE_DDL = """
CREATE TABLE IF NOT EXISTS incident_state (
    service_id       TEXT PRIMARY KEY,
    current_health   TEXT NOT NULL DEFAULT 'healthy',
    incident_start   TIMESTAMPTZ,
    incident_id      TEXT,
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incident_open
    ON incident_state (incident_start)
    WHERE incident_start IS NOT NULL;
"""

# ─────────────────────────────────────────────────────────────────────
# Register all new DDL in the list that run_migrations() iterates.
# If your existing schemas.py has a list like `ALL_DDL = [...]`, append
# these. If it uses a function, call these from there.
# ─────────────────────────────────────────────────────────────────────
BATCH1_DDL = [
    RULES_DDL,
    DECISION_LOG_DDL,
    SHADOW_RECORDS_DDL,
    ESCALATIONS_DDL,
    ACTION_HISTORY_DDL,
    IN_FLIGHT_ACTIONS_DDL,
    INCIDENT_STATE_DDL,       
]

# ─────────────────────────────────────────────────────────────────────
# BATCH 2 — Hybrid Rule Management. Runs AFTER Batch 1 so RULES_DDL has
# already created the base table.
# ─────────────────────────────────────────────────────────────────────
BATCH2_DDL = [
    RULES_HYBRID_DDL,
    RULE_AUDIT_DDL,
]