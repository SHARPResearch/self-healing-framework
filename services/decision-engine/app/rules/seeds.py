"""
Seed rules — inserted into Postgres on first boot (if table is empty).

Two lists:

SEED_RULES — the 8 default rules (`is_default = TRUE`). SHARP owns them:
they can be toggled and customized (thresholds/priority/guardrails) but
never deleted, and their action is frozen.

    1. restart_pod_high_cpu          domain, bff    cpu high, degraded
    2. scale_deployment_high_rps     bff, domain    saturation high, latency rising
    3. open_circuit_breaker          edge           downstream error rate high
    4. flush_cache_stale             data           cache hit low, mem high
    5. increase_db_pool              data           pool near max, p95 high
    6. scale_kafka_consumers         data           queue depth high
    7. rollback_bad_deploy           any            anomaly <5min after deploy
    8. restart_pod_crash_loop        any            repeated restarts, unhealthy

SEED_TEMPLATES — 3 read-only starting points (`is_template = TRUE`).
Never evaluated by the engine, never editable; the UI offers "Clone as
Custom Rule" instead.

Edit these files to change the starter set. Existing rules in DB are NOT
overwritten — use POST /api/rules/reload to re-read from DB.
"""
from app.rules.models import (
    ActionType, RiskLevel,
)

# ─────────────────────────────────────────────────────────────────────
# Each entry is exactly what Rule.model_validate() expects.
# ─────────────────────────────────────────────────────────────────────
SEED_RULES: list[dict] = [
    # ─────────────────────────────────────────────────────────────
    # 1. RESTART_POD on high CPU
    # ─────────────────────────────────────────────────────────────
    {
        "id": "restart_pod_high_cpu",
        "version": 1,
        "priority": 100,
        "description": "Restart pod when CPU is saturated and service is degraded/down",
        "enabled": True,
        "is_default": True,
        "applies_to": {
            "layers": ["domain", "bff"],
            "services": ["*"],
            "exclude_services": ["postgres-primary", "redis-cache", "kafka-broker"],
        },
        "when": {
            "all": [
                {"metric": "anomaly.severity",   "op": "in", "value": ["high", "medium"]},
                {"metric": "anomaly.score",      "op": ">=", "value": 0.60},
                {"metric": "service.health",     "op": "in", "value": ["degraded", "down"]},
                {"metric": "infra.cpu.usage_pct","op": ">=", "value": 0.75},
            ]
        },
        "then": {
            "action": "RESTART_POD",
            "params": {
                "namespace": "{{ service.namespace }}",
                "selector":  "app={{ service.id }}",
                "grace_period_seconds": 30,
            },
            "base_confidence": 0.80,
            "base_risk": "MEDIUM",
        },
        "guardrails": {
            "cooldown_seconds": 300,
            "max_per_hour": 3,
            "idempotency_key": "restart:{{ service.id }}:{{ anomaly.id }}",
        },
        "tags": ["cpu", "restart"],
    },

    # ─────────────────────────────────────────────────────────────
    # 2. SCALE_UP on high saturation / rising latency
    # ─────────────────────────────────────────────────────────────
    {
        "id": "scale_deployment_high_rps",
        "version": 1,
        "priority": 95,
        "description": "Scale up when request saturation is high and latency is rising",
        "enabled": True,
        "is_default": True,
        "applies_to": {
            "layers": ["bff", "domain"],
            "services": ["*"],
            "exclude_services": [],
        },
        "when": {
            "all": [
                {"metric": "anomaly.score",       "op": ">=", "value": 0.55},
                {"metric": "app.saturation_pct",  "op": ">=", "value": 0.80},
                {"metric": "service.health",      "op": "in", "value": ["degraded"]},
            ]
        },
        "then": {
            "action": "SCALE_UP",
            "params": {
                "namespace": "{{ service.namespace }}",
                "deployment": "{{ service.id }}",
                "replicas_delta": 2,
                "max_replicas": 20,
            },
            "base_confidence": 0.78,
            "base_risk": "LOW",
        },
        "guardrails": {
            "cooldown_seconds": 180,
            "max_per_hour": 6,
            "idempotency_key": "scaleup:{{ service.id }}:{{ anomaly.id }}",
        },
        "tags": ["scale", "throughput"],
    },

    # ─────────────────────────────────────────────────────────────
    # 3. OPEN_CIRCUIT on edge service when downstream error rate is high
    # ─────────────────────────────────────────────────────────────
    {
        "id": "open_circuit_breaker",
        "version": 1,
        "priority": 110,
        "description": "Open circuit breaker on edge when downstream error rate spikes",
        "enabled": True,
        "is_default": True,
        "applies_to": {
            "layers": ["edge"],
            "services": ["api-gateway", "waf-proxy"],
            "exclude_services": [],
        },
        "when": {
            "any": [
                {"metric": "app.error_rate",       "op": ">=", "value": 0.05},
                {"metric": "anomaly.deviation_sigma", "op": ">=", "value": 4.0},
            ]
        },
        "then": {
            "action": "OPEN_CIRCUIT",
            "params": {
                "upstream_service": "{{ service.id }}",
                "target_service":   "{{ anomaly.downstream_hint }}",
                "trip_duration_seconds": 60,
            },
            "base_confidence": 0.82,
            "base_risk": "HIGH",
        },
        "guardrails": {
            "cooldown_seconds": 120,
            "max_per_hour": 4,
            "idempotency_key": "circuit:{{ service.id }}",
        },
        "tags": ["circuit", "edge", "blast"],
    },

    # ─────────────────────────────────────────────────────────────
    # 4. FLUSH_CACHE when Redis hit-rate collapses
    # ─────────────────────────────────────────────────────────────
    {
        "id": "flush_cache_stale",
        "version": 1,
        "priority": 90,
        "description": "Flush cache when hit rate collapses and memory is high",
        "enabled": True,
        "is_default": True,
        "applies_to": {
            "layers": ["data"],
            "services": ["redis-cache"],
            "exclude_services": [],
        },
        "when": {
            "all": [
                {"metric": "app.cache_hit_rate",  "op": "<=", "value": 0.50},
                {"metric": "infra.memory.pct",    "op": ">=", "value": 0.75},
            ]
        },
        "then": {
            "action": "FLUSH_CACHE",
            "params": {
                "namespace": "{{ service.namespace }}",
                "selector":  "app={{ service.id }}",
                "pattern":   "stale:*",
            },
            "base_confidence": 0.75,
            "base_risk": "MEDIUM",
        },
        "guardrails": {
            "cooldown_seconds": 600,
            "max_per_hour": 2,
            "idempotency_key": "flush:{{ service.id }}",
        },
        "tags": ["cache", "data"],
    },

    # ─────────────────────────────────────────────────────────────
    # 5. INCREASE_DB_POOL on Postgres when pool near max and p95 high
    # ─────────────────────────────────────────────────────────────
    {
        "id": "increase_db_pool",
        "version": 1,
        "priority": 88,
        "description": "Increase DB connection pool when near saturation and p95 rising",
        "enabled": True,
        "is_default": True,
        "applies_to": {
            "layers": ["data"],
            "services": ["postgres-primary"],
            "exclude_services": [],
        },
        "when": {
            "all": [
                {"metric": "app.db_query_p95_ms",          "op": ">=", "value": 40},
                {"metric": "app.db_connection_pool_used",  "op": ">=", "value": 35},
                {"metric": "service.health",               "op": "in", "value": ["degraded", "down"]},
            ]
        },
        "then": {
            "action": "INCREASE_DB_POOL",
            "params": {
                "target": "postgres-primary",
                "pool_delta": 20,
                "max_pool":   200,
            },
            "base_confidence": 0.77,
            "base_risk": "MEDIUM",
        },
        "guardrails": {
            "cooldown_seconds": 600,
            "max_per_hour": 2,
            "idempotency_key": "dbpool:{{ service.id }}",
        },
        "tags": ["db", "pool"],
    },

    # ─────────────────────────────────────────────────────────────
    # 6. SCALE_CONSUMERS on Kafka when queue depth is high
    # ─────────────────────────────────────────────────────────────
    {
        "id": "scale_kafka_consumers",
        "version": 1,
        "priority": 85,
        "description": "Scale Kafka consumers when broker queue depth is high",
        "enabled": True,
        "is_default": True,
        "applies_to": {
            "layers": ["data"],
            "services": ["kafka-broker"],
            "exclude_services": [],
        },
        "when": {
            "all": [
                {"metric": "app.queue_depth", "op": ">=", "value": 100},
                {"metric": "service.health",  "op": "in", "value": ["degraded", "down"]},
            ]
        },
        "then": {
            "action": "SCALE_CONSUMERS",
            "params": {
                "target": "kafka-broker",
                "consumer_group_hint": "default",
                "consumer_delta": 3,
                "max_consumers": 30,
            },
            "base_confidence": 0.74,
            "base_risk": "LOW",
        },
        "guardrails": {
            "cooldown_seconds": 300,
            "max_per_hour": 4,
            "idempotency_key": "kafka-scale:{{ service.id }}",
        },
        "tags": ["kafka", "queue"],
    },

    # ─────────────────────────────────────────────────────────────
    # 7. ROLLBACK when anomaly follows a recent deploy
    # ─────────────────────────────────────────────────────────────
    {
        "id": "rollback_bad_deploy",
        "version": 1,
        "priority": 130,
        "description": "Rollback when anomaly appears within 5 min of a fresh deploy",
        "enabled": True,
        "is_default": True,
        "applies_to": {
            "layers": ["edge", "bff", "domain"],
            "services": ["*"],
            "exclude_services": [],
        },
        "when": {
            "all": [
                {"metric": "anomaly.severity", "op": "in", "value": ["high"]},
                {"metric": "infra.uptime_seconds", "op": "<=", "value": 300},
                {"metric": "anomaly.score", "op": ">=", "value": 0.85},
            ]
        },
        "then": {
            "action": "ROLLBACK",
            "params": {
                "namespace": "{{ service.namespace }}",
                "deployment": "{{ service.id }}",
                "reason": "anomaly_within_5min_of_deploy",
            },
            "base_confidence": 0.85,
            "base_risk": "HIGH",
        },
        "guardrails": {
            "cooldown_seconds": 900,
            "max_per_hour": 1,
            "idempotency_key": "rollback:{{ service.id }}:{{ anomaly.id }}",
        },
        "tags": ["deploy", "rollback"],
    },

    # ─────────────────────────────────────────────────────────────
    # 8. RESTART_POD on crash-loop (repeated restarts in 5m)
    # ─────────────────────────────────────────────────────────────
    {
        "id": "restart_pod_crash_loop",
        "version": 1,
        "priority": 120,
        "description": "Restart pod when it keeps crash-looping and the service is unhealthy",
        "enabled": True,
        "is_default": True,
        "applies_to": {
            "layers": ["edge", "bff", "domain"],
            "services": ["*"],
            "exclude_services": ["postgres-primary", "kafka-broker"],
        },
        "when": {
            "all": [
                {"metric": "infra.restarts_last_5m", "op": ">=", "value": 3},
                {"metric": "service.health",         "op": "in", "value": ["degraded", "down"]},
                {"metric": "anomaly.score",          "op": ">=", "value": 0.55},
            ]
        },
        "then": {
            "action": "RESTART_POD",
            "params": {
                "namespace": "{{ service.namespace }}",
                "selector":  "app={{ service.id }}",
                "grace_period_seconds": 15,
                "reason": "crash_loop_detected",
            },
            "base_confidence": 0.83,
            "base_risk": "MEDIUM",
        },
        "guardrails": {
            "cooldown_seconds": 240,
            "max_per_hour": 3,
            "idempotency_key": "crashloop:{{ service.id }}:{{ anomaly.id }}",
        },
        "tags": ["restart", "crash-loop"],
    },
]


# ─────────────────────────────────────────────────────────────────────
# Template rules — read-only starting points offered by SHARP.
#
# They are NEVER evaluated by the engine (the registry skips
# is_template = TRUE rows) and they cannot be edited or deleted through
# the API. The UI shows them under the "Templates" tab and offers
# "Clone as Custom Rule" only.
# ─────────────────────────────────────────────────────────────────────
SEED_TEMPLATES: list[dict] = [
    {
        "id": "template_scale_on_latency",
        "version": 1,
        "priority": 100,
        "description": "Template: scale up a service when p95 latency blows past its SLO",
        "enabled": True,
        "is_default": False,
        "is_template": True,
        "created_by": "system",
        "applies_to": {
            "layers": ["edge", "bff", "domain"],
            "services": ["*"],
            "exclude_services": [],
        },
        "when": {
            "all": [
                {"metric": "app.latency_ms.p95", "op": ">=", "value": 750},
                {"metric": "anomaly.score",     "op": ">=", "value": 0.55},
            ]
        },
        "then": {
            "action": "SCALE_UP",
            "params": {
                "namespace": "{{ service.namespace }}",
                "deployment": "{{ service.id }}",
                "replicas_delta": 2,
                "max_replicas": 20,
            },
            "base_confidence": 0.75,
            "base_risk": "LOW",
        },
        "guardrails": {
            "cooldown_seconds": 300,
            "max_per_hour": 4,
            "idempotency_key": "scaleup-latency:{{ service.id }}",
        },
        "tags": ["template", "latency", "scale"],
    },
    {
        "id": "template_restart_on_error_rate",
        "version": 1,
        "priority": 100,
        "description": "Template: restart a service when its 5xx error rate spikes",
        "enabled": True,
        "is_default": False,
        "is_template": True,
        "created_by": "system",
        "applies_to": {
            "layers": ["edge", "bff", "domain"],
            "services": ["*"],
            "exclude_services": [],
        },
        "when": {
            "all": [
                {"metric": "app.error_rate",  "op": ">=", "value": 0.10},
                {"metric": "anomaly.severity", "op": "in", "value": ["high"]},
            ]
        },
        "then": {
            "action": "RESTART_POD",
            "params": {
                "namespace": "{{ service.namespace }}",
                "selector":  "app={{ service.id }}",
                "grace_period_seconds": 30,
            },
            "base_confidence": 0.72,
            "base_risk": "MEDIUM",
        },
        "guardrails": {
            "cooldown_seconds": 420,
            "max_per_hour": 2,
            "idempotency_key": "restart-err:{{ service.id }}",
        },
        "tags": ["template", "errors", "restart"],
    },
    {
        "id": "template_scale_consumers_on_lag",
        "version": 1,
        "priority": 100,
        "description": "Template: add consumers when the queue is backing up",
        "enabled": True,
        "is_default": False,
        "is_template": True,
        "created_by": "system",
        "applies_to": {
            "layers": ["data"],
            "services": ["kafka-broker"],
            "exclude_services": [],
        },
        "when": {
            "all": [
                {"metric": "app.queue_depth", "op": ">=", "value": 50},
                {"metric": "anomaly.score",   "op": ">=", "value": 0.50},
            ]
        },
        "then": {
            "action": "SCALE_CONSUMERS",
            "params": {
                "target": "kafka-broker",
                "consumer_group_hint": "default",
                "consumer_delta": 2,
                "max_consumers": 30,
            },
            "base_confidence": 0.74,
            "base_risk": "LOW",
        },
        "guardrails": {
            "cooldown_seconds": 300,
            "max_per_hour": 4,
            "idempotency_key": "kafka-lag:{{ service.id }}",
        },
        "tags": ["template", "kafka", "queue"],
    },
]