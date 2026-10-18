"""
Seed rules — inserted into Postgres on first boot (if table is empty).

These are the initial 7 rules covering the 15-service topology:

    1. restart_pod_high_cpu          domain, bff    cpu high, degraded
    2. scale_deployment_high_rps     bff, domain    saturation high, latency rising
    3. open_circuit_breaker          edge           downstream error rate high
    4. flush_cache_stale             data           cache hit low, mem high
    5. increase_db_pool              data           pool near max, p95 high
    6. scale_kafka_consumers         data           queue depth high
    7. rollback_bad_deploy           any            anomaly <5min after deploy

Edit this file to change the starter set. Existing rules in DB are NOT
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
]