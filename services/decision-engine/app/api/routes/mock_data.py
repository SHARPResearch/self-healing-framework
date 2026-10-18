"""
Advanced mock telemetry — Component 1 will replace this later.

Generates realistic-looking infra, application, and anomaly data for a
15-service microservice mesh. Every service has its own baseline profile
so values differ meaningfully across the graph.

Scenario endpoints let you flip the entire mesh into different failure
modes for demoing the decision engine.
"""
# from collections import defaultdict
from fastapi import APIRouter, Query
from datetime import datetime, timezone, timedelta
from typing import Literal
import random
import math

router = APIRouter(prefix="/api", tags=["mock"])

# ─────────────────────────────────────────────────────────────────────
# SERVICE CATALOG — 15 services in 4 layers
# ─────────────────────────────────────────────────────────────────────
SERVICES = {
    # ── Edge / Gateway layer ────────────────────────────────────────
    "api-gateway": {
        "display_name": "API Gateway",
        "layer": "edge",
        "team": "platform",
        "tier": 0,
        "runtime": "envoy",
        "version": "1.24.1",
        "region": "us-east-1a",
        "node_pool": "edge-pool",
        "replicas": 6,
        "cpu_limit_mc": 500, "mem_limit_mb": 512,
        "base_cpu": 0.42, "base_mem_mb": 380, "base_rps": 820.0,
        "base_p50": 8.0, "base_p95": 32.0, "base_p99": 95.0,
        "base_err": 0.0015, "base_conns": 640, "base_db_p95": 0, "base_cache": 0.0,
        "base_queue": 0,
    },
    "waf-proxy": {
        "display_name": "WAF Proxy",
        "layer": "edge",
        "team": "security",
        "tier": 0,
        "runtime": "nginx",
        "version": "1.27.2",
        "region": "us-east-1a",
        "node_pool": "edge-pool",
        "replicas": 4,
        "cpu_limit_mc": 400, "mem_limit_mb": 384,
        "base_cpu": 0.28, "base_mem_mb": 210, "base_rps": 810.0,
        "base_p50": 3.0, "base_p95": 12.0, "base_p99": 28.0,
        "base_err": 0.0008, "base_conns": 720, "base_db_p95": 0, "base_cache": 0.0,
        "base_queue": 0,
    },

    # ── BFF layer ───────────────────────────────────────────────────
    "web-bff": {
        "display_name": "Web BFF",
        "layer": "bff",
        "team": "web",
        "tier": 1,
        "runtime": "node20",
        "version": "3.8.4",
        "region": "us-east-1a",
        "node_pool": "app-pool",
        "replicas": 4,
        "cpu_limit_mc": 800, "mem_limit_mb": 1024,
        "base_cpu": 0.38, "base_mem_mb": 560, "base_rps": 620.0,
        "base_p50": 15.0, "base_p95": 60.0, "base_p99": 180.0,
        "base_err": 0.003, "base_conns": 380, "base_db_p95": 0, "base_cache": 0.88,
        "base_queue": 4,
    },
    "mobile-bff": {
        "display_name": "Mobile BFF",
        "layer": "bff",
        "team": "mobile",
        "tier": 1,
        "runtime": "node20",
        "version": "3.7.1",
        "region": "us-east-1a",
        "node_pool": "app-pool",
        "replicas": 4,
        "cpu_limit_mc": 800, "mem_limit_mb": 1024,
        "base_cpu": 0.34, "base_mem_mb": 480, "base_rps": 510.0,
        "base_p50": 18.0, "base_p95": 72.0, "base_p99": 210.0,
        "base_err": 0.004, "base_conns": 320, "base_db_p95": 0, "base_cache": 0.85,
        "base_queue": 6,
    },

    # ── Domain services ────────────────────────────────────────────
    "auth-service": {
        "display_name": "Auth Service",
        "layer": "domain",
        "team": "identity",
        "tier": 1,
        "runtime": "go1.22",
        "version": "5.2.0",
        "region": "us-east-1a",
        "node_pool": "app-pool",
        "replicas": 4,
        "cpu_limit_mc": 600, "mem_limit_mb": 512,
        "base_cpu": 0.22, "base_mem_mb": 260, "base_rps": 420.0,
        "base_p50": 6.0, "base_p95": 22.0, "base_p99": 55.0,
        "base_err": 0.001, "base_conns": 210, "base_db_p95": 12, "base_cache": 0.92,
        "base_queue": 0,
    },
    "user-service": {
        "display_name": "User Service",
        "layer": "domain",
        "team": "identity",
        "tier": 2,
        "runtime": "go1.22",
        "version": "4.1.3",
        "region": "us-east-1a",
        "node_pool": "app-pool",
        "replicas": 3,
        "cpu_limit_mc": 500, "mem_limit_mb": 512,
        "base_cpu": 0.20, "base_mem_mb": 240, "base_rps": 280.0,
        "base_p50": 10.0, "base_p95": 38.0, "base_p99": 95.0,
        "base_err": 0.002, "base_conns": 140, "base_db_p95": 22, "base_cache": 0.86,
        "base_queue": 0,
    },
    "orders-service": {
        "display_name": "Orders Service",
        "layer": "domain",
        "team": "commerce",
        "tier": 2,
        "runtime": "java21",
        "version": "8.4.1",
        "region": "us-east-1a",
        "node_pool": "jvm-pool",
        "replicas": 5,
        "cpu_limit_mc": 1500, "mem_limit_mb": 2048,
        "base_cpu": 0.45, "base_mem_mb": 1280, "base_rps": 240.0,
        "base_p50": 28.0, "base_p95": 105.0, "base_p99": 265.0,
        "base_err": 0.004, "base_conns": 260, "base_db_p95": 48, "base_cache": 0.74,
        "base_queue": 8,
    },
    "payment-service": {
        "display_name": "Payment Service",
        "layer": "domain",
        "team": "payments",
        "tier": 2,
        "runtime": "java21",
        "version": "6.9.2",
        "region": "us-east-1a",
        "node_pool": "jvm-pool",
        "replicas": 4,
        "cpu_limit_mc": 1500, "mem_limit_mb": 2048,
        "base_cpu": 0.32, "base_mem_mb": 890, "base_rps": 95.0,
        "base_p50": 42.0, "base_p95": 155.0, "base_p99": 420.0,
        "base_err": 0.0025, "base_conns": 130, "base_db_p95": 72, "base_cache": 0.79,
        "base_queue": 3,
    },
    "inventory-service": {
        "display_name": "Inventory Service",
        "layer": "domain",
        "team": "supply",
        "tier": 2,
        "runtime": "python3.12",
        "version": "2.6.0",
        "region": "us-east-1a",
        "node_pool": "app-pool",
        "replicas": 3,
        "cpu_limit_mc": 800, "mem_limit_mb": 1024,
        "base_cpu": 0.19, "base_mem_mb": 340, "base_rps": 110.0,
        "base_p50": 22.0, "base_p95": 78.0, "base_p99": 190.0,
        "base_err": 0.0015, "base_conns": 95, "base_db_p95": 38, "base_cache": 0.90,
        "base_queue": 2,
    },
    "shipping-service": {
        "display_name": "Shipping Service",
        "layer": "domain",
        "team": "logistics",
        "tier": 3,
        "runtime": "go1.22",
        "version": "3.4.7",
        "region": "us-east-1a",
        "node_pool": "app-pool",
        "replicas": 3,
        "cpu_limit_mc": 500, "mem_limit_mb": 512,
        "base_cpu": 0.24, "base_mem_mb": 290, "base_rps": 130.0,
        "base_p50": 30.0, "base_p95": 110.0, "base_p99": 280.0,
        "base_err": 0.003, "base_conns": 110, "base_db_p95": 55, "base_cache": 0.70,
        "base_queue": 5,
    },
    "notification-service": {
        "display_name": "Notification Service",
        "layer": "domain",
        "team": "engagement",
        "tier": 3,
        "runtime": "python3.12",
        "version": "1.9.3",
        "region": "us-east-1a",
        "node_pool": "app-pool",
        "replicas": 3,
        "cpu_limit_mc": 600, "mem_limit_mb": 768,
        "base_cpu": 0.15, "base_mem_mb": 320, "base_rps": 340.0,
        "base_p50": 12.0, "base_p95": 45.0, "base_p99": 120.0,
        "base_err": 0.006, "base_conns": 200, "base_db_p95": 18, "base_cache": 0.82,
        "base_queue": 12,
    },
    "search-service": {
        "display_name": "Search Service",
        "layer": "domain",
        "team": "discovery",
        "tier": 3,
        "runtime": "rust1.79",
        "version": "4.2.1",
        "region": "us-east-1a",
        "node_pool": "app-pool",
        "replicas": 4,
        "cpu_limit_mc": 1000, "mem_limit_mb": 1536,
        "base_cpu": 0.29, "base_mem_mb": 720, "base_rps": 380.0,
        "base_p50": 14.0, "base_p95": 55.0, "base_p99": 145.0,
        "base_err": 0.002, "base_conns": 240, "base_db_p95": 26, "base_cache": 0.93,
        "base_queue": 1,
    },

    # ── Data layer ─────────────────────────────────────────────────
    "postgres-primary": {
        "display_name": "Postgres Primary",
        "layer": "data",
        "team": "data-platform",
        "tier": 1,
        "runtime": "postgres16",
        "version": "16.3",
        "region": "us-east-1a",
        "node_pool": "db-pool",
        "replicas": 1,
        "cpu_limit_mc": 4000, "mem_limit_mb": 8192,
        "base_cpu": 0.52, "base_mem_mb": 5200, "base_rps": 4200.0,
        "base_p50": 4.0, "base_p95": 18.0, "base_p99": 55.0,
        "base_err": 0.0004, "base_conns": 480, "base_db_p95": 4, "base_cache": 0.0,
        "base_queue": 0,
    },
    "redis-cache": {
        "display_name": "Redis Cache",
        "layer": "data",
        "team": "data-platform",
        "tier": 1,
        "runtime": "redis7",
        "version": "7.2.4",
        "region": "us-east-1a",
        "node_pool": "db-pool",
        "replicas": 3,
        "cpu_limit_mc": 2000, "mem_limit_mb": 4096,
        "base_cpu": 0.18, "base_mem_mb": 2100, "base_rps": 12000.0,
        "base_p50": 0.4, "base_p95": 1.2, "base_p99": 3.5,
        "base_err": 0.0001, "base_conns": 890, "base_db_p95": 0, "base_cache": 0.0,
        "base_queue": 0,
    },
    "kafka-broker": {
        "display_name": "Kafka Broker",
        "layer": "data",
        "team": "data-platform",
        "tier": 1,
        "runtime": "kafka3.7",
        "version": "3.7.0",
        "region": "us-east-1a",
        "node_pool": "db-pool",
        "replicas": 3,
        "cpu_limit_mc": 3000, "mem_limit_mb": 6144,
        "base_cpu": 0.31, "base_mem_mb": 3200, "base_rps": 8500.0,
        "base_p50": 2.0, "base_p95": 8.0, "base_p99": 22.0,
        "base_err": 0.0002, "base_conns": 420, "base_db_p95": 0, "base_cache": 0.0,
        "base_queue": 45,
    },
}

SERVICE_IDS = list(SERVICES.keys())


# ─────────────────────────────────────────────────────────────────────
# TOPOLOGY — who calls whom
# ─────────────────────────────────────────────────────────────────────
EDGES = [
    # edge -> bff
    ("waf-proxy", "api-gateway"),
    ("api-gateway", "web-bff"),
    ("api-gateway", "mobile-bff"),

    # bff -> domain
    ("web-bff", "auth-service"),
    ("web-bff", "orders-service"),
    ("web-bff", "search-service"),
    ("mobile-bff", "auth-service"),
    ("mobile-bff", "orders-service"),

    # domain -> domain
    ("orders-service", "payment-service"),
    ("orders-service", "inventory-service"),
    ("orders-service", "shipping-service"),
    ("orders-service", "notification-service"),
    ("auth-service", "user-service"),
    ("payment-service", "notification-service"),
    ("shipping-service", "notification-service"),
    ("search-service", "inventory-service"),
    ("search-service", "user-service"),

    # domain -> data
    ("auth-service", "postgres-primary"),
    ("auth-service", "redis-cache"),
    ("user-service", "postgres-primary"),
    ("user-service", "redis-cache"),
    ("orders-service", "postgres-primary"),
    ("orders-service", "redis-cache"),
    ("orders-service", "kafka-broker"),
    ("payment-service", "postgres-primary"),
    ("payment-service", "kafka-broker"),
    ("inventory-service", "postgres-primary"),
    ("inventory-service", "redis-cache"),
    ("shipping-service", "postgres-primary"),
    ("notification-service", "kafka-broker"),
    ("search-service", "redis-cache"),
]


# ─────────────────────────────────────────────────────────────────────
# SCENARIOS
# ─────────────────────────────────────────────────────────────────────
SCENARIOS = {
    "all_healthy": {},

    # Single service pain, no cascade
    "isolated_orders_slow": {
        "orders-service": "failing",
    },

    # Auth fails -> cascades to both BFFs, gateways
    "auth_outage": {
        "auth-service": "failing",
        "user-service": "degraded",
        "web-bff": "degraded",
        "mobile-bff": "degraded",
        "api-gateway": "degraded",
    },

    # Database pain -> everything that talks to it degrades
    "database_degraded": {
        "postgres-primary": "failing",
        "auth-service": "degraded",
        "user-service": "degraded",
        "orders-service": "degraded",
        "payment-service": "degraded",
        "inventory-service": "degraded",
    },

    # Payment slow -> orders BFF slow -> edge slow
    "payment_slowdown": {
        "payment-service": "failing",
        "orders-service": "degraded",
        "web-bff": "degraded",
        "api-gateway": "degraded",
    },

    # Cache cluster pain -> search + auth degrade
    "cache_outage": {
        "redis-cache": "failing",
        "search-service": "degraded",
        "auth-service": "degraded",
        "user-service": "degraded",
    },

    # Kafka lag -> notifications + orders
    "kafka_lag": {
        "kafka-broker": "degraded",
        "notification-service": "degraded",
        "orders-service": "degraded",
    },

    # Edge overwhelmed -> all user traffic affected
    "edge_overload": {
        "api-gateway": "failing",
        "web-bff": "degraded",
        "mobile-bff": "degraded",
    },
}
CURRENT_SCENARIO = "all_healthy"
# ANOMALY_SEQUENCE = defaultdict(int)


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _health(sid: str) -> str:
    return SCENARIOS[CURRENT_SCENARIO].get(sid, "healthy")


def _jitter(base: float, pct: float = 0.05) -> float:
    return base * (1 + random.uniform(-pct, pct))


def _deterministic_hash(sid: str) -> int:
    """Stable pseudo-hash so a service always maps to the same node/IP."""
    h = 0
    for ch in sid:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def _apply_health_multipliers(health: str) -> dict:
    """Return multipliers for each metric dimension based on health."""
    if health == "failing":
        return {
            "cpu": 3.0, "mem": 2.2, "lat": 9.0, "err": 55.0,
            "ready_drop": 2, "restarts": 2, "queue": 12.0,
            "db": 6.0, "cache_drop": 0.35,
        }
    if health == "degraded":
        return {
            "cpu": 1.9, "mem": 1.5, "lat": 3.2, "err": 14.0,
            "ready_drop": 1, "restarts": 1, "queue": 4.0,
            "db": 2.8, "cache_drop": 0.15,
        }
    return {
        "cpu": 1.0, "mem": 1.0, "lat": 1.0, "err": 1.0,
        "ready_drop": 0, "restarts": 0, "queue": 1.0,
        "db": 1.0, "cache_drop": 0.0,
    }


# ─────────────────────────────────────────────────────────────────────
# ANOMALY
# ─────────────────────────────────────────────────────────────────────
def _anomaly(sid: str):
    health = _health(sid)
    if health == "healthy":
        return None

    p = SERVICES[sid]
    m = _apply_health_multipliers(health)

    score = round(
        random.uniform(0.85, 0.98) if health == "failing" else random.uniform(0.6, 0.8),
        2,
    )

    metric_choice = random.choice([
        ("request_latency_p99", p["base_p99"] * m["lat"], p["base_p99"]),
        ("cpu_usage_pct",       p["base_cpu"] * m["cpu"], p["base_cpu"]),
        ("error_rate",          p["base_err"] * m["err"], p["base_err"]),
    ])

    # Unique per anomaly occurrence, but still human-readable and grouped by day/service.
    # today = datetime.now(timezone.utc).strftime("%Y%m%d")
    # ANOMALY_SEQUENCE[(CURRENT_SCENARIO, sid, today)] += 1
    # occurrence = ANOMALY_SEQUENCE[(CURRENT_SCENARIO, sid, today)]
    # Stable per (scenario, service, hour)
    hour = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    stable_id = f"ANM-{CURRENT_SCENARIO}-{sid}-{hour}"

    return {
        "id": stable_id,
        "service_id": sid,
        "service_name": p["display_name"],
        "team": p["team"],
        "layer": p["layer"],
        "anomaly_score": score,
        "severity": "high" if score >= 0.85 else "medium" if score >= 0.6 else "low",
        "metric": metric_choice[0],
        "actual_value": round(metric_choice[1], 3),
        "expected_value": round(metric_choice[2], 3),
        "deviation_sigma": round(4.2 if health == "failing" else 2.4, 2),
        "detected_at": _now(),
        "model_version": "hst-v3.2",
        "confidence": round(random.uniform(0.85, 0.99), 3),
        "features": {
            "cpu_pct": round(min(0.99, p["base_cpu"] * m["cpu"]), 3),
            "mem_mb": int(p["base_mem_mb"] * m["mem"]),
            "error_rate": round(min(0.95, p["base_err"] * m["err"]), 4),
            "p99_ms": round(p["base_p99"] * m["lat"], 1),
        },
    }

# ─────────────────────────────────────────────────────────────────────
# INFRA
# ─────────────────────────────────────────────────────────────────────
def _infra(sid: str) -> dict:
    p = SERVICES[sid]
    health = _health(sid)
    m = _apply_health_multipliers(health)

    cpu = min(0.98, _jitter(p["base_cpu"] * m["cpu"], 0.08))
    mem_used = int(_jitter(p["base_mem_mb"] * m["mem"], 0.04))
    mem_limit = p["mem_limit_mb"]

    # Container age decreases when pod restarts
    uptime_seconds = random.randint(60, 86400) if m["restarts"] else random.randint(3600, 604800)

    return {
        "service_id": sid,
        "service_name": p["display_name"],
        "layer": p["layer"],
        "team": p["team"],
        "runtime": p["runtime"],
        "version": p["version"],
        "region": p["region"],
        "node_pool": p["node_pool"],
        "node": f"ip-10-0-{1 + (_deterministic_hash(sid) % 3)}-{40 + (_deterministic_hash(sid) % 200)}",
        "container_image": f"registry.internal/{p['team']}/{sid}:{p['version']}",
        "uptime_seconds": uptime_seconds,

        # ── Pods ────────────────────────────────────────────────────
        "pod_count": p["replicas"],
        "ready_pods": max(0, p["replicas"] - m["ready_drop"]),
        "restarts_last_5m": m["restarts"],

        # ── CPU ─────────────────────────────────────────────────────
        "cpu": {
            "usage_pct": round(cpu, 3),
            "cores_used": round(cpu * (p["cpu_limit_mc"] / 1000), 3),
            "limit_cores": round(p["cpu_limit_mc"] / 1000, 2),
            "throttled_pct": round(min(1.0, cpu * 0.15 if cpu > 0.7 else 0.0), 3),
        },

        # ── Memory ──────────────────────────────────────────────────
        "memory": {
            "used_mb": mem_used,
            "limit_mb": mem_limit,
            "pct": round(min(1.0, mem_used / mem_limit), 3),
            "rss_mb": int(mem_used * 0.85),
            "heap_mb": int(mem_used * 0.65) if "java" in p["runtime"] or "node" in p["runtime"] else 0,
            "oom_kills": 1 if health == "failing" and mem_used / mem_limit > 0.9 else 0,
        },

        # ── Network ─────────────────────────────────────────────────
        "network": {
            "rx_kbps": int(_jitter(p["base_rps"] * 6, 0.15)),
            "tx_kbps": int(_jitter(p["base_rps"] * 3, 0.15)),
            "rx_errors": int(random.uniform(0, 5 if health == "failing" else 1)),
            "tx_dropped": int(random.uniform(0, 3 if health == "degraded" else 0)),
        },

        # ── Disk (only meaningful for data services) ────────────────
        "disk": {
            "read_iops": int(_jitter(200 if p["layer"] == "data" else 20, 0.2)),
            "write_iops": int(_jitter(150 if p["layer"] == "data" else 12, 0.2)),
            "used_pct": round(min(0.95, 0.45 + random.uniform(-0.05, 0.15)), 3),
        },

        # ── GC (JVM / Node only) ────────────────────────────────────
        "gc": (
            {
                "pause_p95_ms": round(_jitter(12 * m["lat"] * 0.3, 0.2), 1),
                "collections_per_min": int(_jitter(30 * m["cpu"], 0.15)),
            }
            if any(r in p["runtime"] for r in ("java", "node"))
            else None
        ),

        "timestamp": _now(),
    }


# ─────────────────────────────────────────────────────────────────────
# APPLICATION
# ─────────────────────────────────────────────────────────────────────
def _app(sid: str) -> dict:
    p = SERVICES[sid]
    health = _health(sid)
    m = _apply_health_multipliers(health)

    p50 = _jitter(p["base_p50"] * m["lat"], 0.10)
    p95 = _jitter(p["base_p95"] * m["lat"], 0.08)
    p99 = _jitter(p["base_p99"] * m["lat"], 0.05)
    rps = _jitter(p["base_rps"], 0.06)
    err = min(0.95, _jitter(p["base_err"] * m["err"], 0.15))
    cache = max(0.0, min(0.99, _jitter(p["base_cache"] - m["cache_drop"], 0.03)))
    queue = int(_jitter(p["base_queue"] * m["queue"], 0.20))

    total = max(1, int(rps))
    err5 = int(total * err)
    err4 = int(total * 0.008)
    ok2 = total - err4 - err5

    # RPS distribution by endpoint (top 3)
    endpoints = []
    if sid == "api-gateway" or sid == "waf-proxy":
        endpoints = [
            {"path": "/api/v1/orders", "rps": int(rps * 0.4), "p99": round(p99 * 1.1, 1)},
            {"path": "/api/v1/auth", "rps": int(rps * 0.25), "p99": round(p99 * 0.7, 1)},
            {"path": "/api/v1/search", "rps": int(rps * 0.2), "p99": round(p99 * 0.9, 1)},
        ]
    elif sid in ("orders-service", "payment-service", "inventory-service"):
        endpoints = [
            {"path": "/orders", "rps": int(rps * 0.55), "p99": round(p99, 1)},
            {"path": "/orders/{id}", "rps": int(rps * 0.3), "p99": round(p99 * 0.8, 1)},
        ]

    return {
        "service_id": sid,
        "service_name": p["display_name"],
        "layer": p["layer"],
        "team": p["team"],

        "timestamp": _now(),
        "requests_per_sec": round(rps, 1),
        "throughput_bytes_per_sec": int(rps * random.uniform(1200, 3200)),

        "latency_ms": {
            "p50": round(p50, 1),
            "p90": round((p50 + p95) / 2, 1),
            "p95": round(p95, 1),
            "p99": round(p99, 1),
            "p999": round(p99 * 1.8, 1),
            "max": round(p99 * 4.2, 1),
        },

        "error_rate": round(err, 4),
        "error_budget_remaining_pct": round(max(0.0, 1 - err / 0.01) * 100, 1),

        "status_codes": {
            "2xx": ok2,
            "3xx": int(total * 0.001),
            "4xx": err4,
            "5xx": err5,
        },

        "active_connections": int(_jitter(p["base_conns"], 0.10)),
        "queue_depth": queue,
        "queue_lag_ms": round(queue * 12.5, 1),

        "db_query_p95_ms": round(_jitter(p["base_db_p95"] * m["db"], 0.10), 1),
        "db_connection_pool_used": int(random.uniform(5, 40)) if p["base_db_p95"] > 0 else 0,
        "db_connection_pool_max": 50 if p["base_db_p95"] > 0 else 0,

        "cache_hit_rate": round(cache, 3),
        "cache_evictions_per_min": int(random.uniform(0, 20 if health != "healthy" else 3)),

        "upstream_calls": [],   # filled by UI based on graph
        "endpoints": endpoints,

        "saturation_pct": round(min(1.0, rps / (p["base_rps"] * 1.2)), 3),
    }


# ─────────────────────────────────────────────────────────────────────
# TIME SERIES (last N points) — for sparkline charts
# ─────────────────────────────────────────────────────────────────────
def _timeseries(sid: str, points: int = 30, metric: str = "p99") -> list[dict]:
    p = SERVICES[sid]
    health = _health(sid)
    m = _apply_health_multipliers(health)

    now = datetime.now(timezone.utc)
    out = []
    for i in range(points, 0, -1):
        ts = (now - timedelta(seconds=i * 10)).isoformat().replace("+00:00", "Z")
        # Ramp effect: if failing, values increase as we approach "now"
        ramp = 1 + (points - i) / points * 0.6 if health != "healthy" else 1

        if metric == "p99":
            value = _jitter(p["base_p99"] * m["lat"] * ramp, 0.10)
        elif metric == "rps":
            value = _jitter(p["base_rps"] * (0.85 + ramp * 0.15), 0.08)
        elif metric == "error_rate":
            value = min(0.95, _jitter(p["base_err"] * m["err"] * ramp, 0.15))
        else:
            value = 0.0

        out.append({"t": ts, "v": round(value, 3)})
    return out


# ─────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────
@router.get("/anomalies/recent")
def anomalies(limit: int = Query(20, ge=1, le=200)):
    out = [a for sid in SERVICE_IDS if (a := _anomaly(sid))]
    out.sort(key=lambda x: x["detected_at"], reverse=True)
    return out[:limit]


@router.get("/infra")
def infra_all():
    return [_infra(sid) for sid in SERVICE_IDS]


@router.get("/infra/{service_id}")
def infra_one(service_id: str):
    if service_id not in SERVICES:
        return {"error": f"unknown service: {service_id}"}
    return _infra(service_id)


@router.get("/app")
def app_all():
    return [_app(sid) for sid in SERVICE_IDS]


@router.get("/app/{service_id}")
def app_one(service_id: str):
    if service_id not in SERVICES:
        return {"error": f"unknown service: {service_id}"}
    return _app(service_id)


@router.get("/timeseries/{service_id}")
def timeseries(
    service_id: str,
    metric: Literal["p99", "rps", "error_rate"] = "p99",
    points: int = Query(30, ge=5, le=120),
):
    if service_id not in SERVICES:
        return {"error": f"unknown service: {service_id}"}
    return {
        "service_id": service_id,
        "metric": metric,
        "points": _timeseries(service_id, points, metric),
    }


@router.get("/services")
def services():
    """Return catalog of all services with metadata."""
    return [
        {
            "service_id": sid,
            "display_name": p["display_name"],
            "layer": p["layer"],
            "team": p["team"],
            "tier": p["tier"],
            "runtime": p["runtime"],
            "version": p["version"],
            "region": p["region"],
            "node_pool": p["node_pool"],
            "replicas": p["replicas"],
            "health": _health(sid),
        }
        for sid, p in SERVICES.items()
    ]


@router.post("/mock/scenario/{name}")
def set_scenario(name: str):
    global CURRENT_SCENARIO
    if name not in SCENARIOS:
        return {"error": f"unknown scenario. try: {list(SCENARIOS)}"}
    CURRENT_SCENARIO = name
    return {"scenario": name, "health": SCENARIOS[name]}


@router.get("/mock/scenario")
def get_scenario():
    return {"current": CURRENT_SCENARIO, "available": list(SCENARIOS)}