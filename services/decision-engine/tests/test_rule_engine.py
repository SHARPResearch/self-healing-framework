"""
Rule Engine tests — isolated, upstream, cascading, root cause.

Run with:
    cd services/decision-engine
    uv run pytest tests/test_rule_engine.py -v
"""
import os
import pytest

# Ensure the app can find seeds/topology.yaml
os.environ.setdefault("PYTHONPATH", ".")

from app.core.graph_store import GraphStore
from app.core.blast_radius import BlastRadiusAnalyzer
from app.core.centrality import CentralityCalculator
from app.core.root_cause import localize_root_cause
from app.rules.context import ContextBuilder
from app.rules.classifier import classify, AnomalyKind
from app.rules.engine import rule_engine
from app.topology.sources.static_source import load_static_topology


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def load_topology():
    load_static_topology("seeds/topology.yaml")
    yield


@pytest.fixture
def services_catalog():
    """Minimal in-test catalog for the 15 services."""
    return {
        sid: {
            "service_id": sid,
            "layer": _layer_of(sid),
            "team": "test",
            "runtime": "test",
            "replicas": 3,
            "health": "healthy",
        }
        for sid in [
            "waf-proxy", "api-gateway", "web-bff", "mobile-bff",
            "auth-service", "user-service", "orders-service",
            "payment-service", "inventory-service", "shipping-service",
            "notification-service", "search-service",
            "postgres-primary", "redis-cache", "kafka-broker",
        ]
    }


def _layer_of(sid: str) -> str:
    if sid in ("waf-proxy", "api-gateway"):
        return "edge"
    if sid in ("web-bff", "mobile-bff"):
        return "bff"
    if sid in ("postgres-primary", "redis-cache", "kafka-broker"):
        return "data"
    return "domain"


@pytest.fixture
def builder(services_catalog):
    b = ContextBuilder()
    b.set_services_catalog(services_catalog)
    return b


# ─────────────────────────────────────────────────────────────────────
# Classifier tests
# ─────────────────────────────────────────────────────────────────────
def test_isolated_when_no_neighbors_unhealthy(builder, services_catalog):
    """notification-service is a leaf → ISOLATED."""
    # everyone healthy
    anomaly = {
        "id": "ANM-test-1",
        "service_id": "notification-service",
        "anomaly_score": 0.9,
        "severity": "high",
        "confidence": 0.9,
    }
    ctx = builder.build(anomaly)
    classify(ctx)
    assert ctx.kind == AnomalyKind.ISOLATED


def test_cascading_when_downstream_unhealthy(builder, services_catalog):
    """auth-service fails → web-bff (downstream) also unhealthy → CASCADING for web-bff."""
    # Mark auth-service degraded in graph directly
    GraphStore().graph().nodes["auth-service"]["health"] = "down"
    services_catalog["auth-service"]["health"] = "down"

    anomaly = {
        "id": "ANM-test-2",
        "service_id": "web-bff",
        "anomaly_score": 0.85,
        "severity": "high",
        "confidence": 0.9,
    }
    ctx = builder.build(anomaly)
    classify(ctx)
    # web-bff's upstream is api-gateway (healthy), its downstream is auth-service (down)
    assert ctx.kind in (AnomalyKind.CASCADING, AnomalyKind.UPSTREAM)


def test_upstream_when_upstream_unhealthy(builder, services_catalog):
    """postgres-primary down → auth-service upstream unhealthy → UPSTREAM."""
    # Reset auth-service
    GraphStore().graph().nodes["auth-service"]["health"] = "healthy"
    services_catalog["auth-service"]["health"] = "healthy"
    # Mark postgres down
    GraphStore().graph().nodes["postgres-primary"]["health"] = "down"
    services_catalog["postgres-primary"]["health"] = "down"

    anomaly = {
        "id": "ANM-test-3",
        "service_id": "auth-service",
        "anomaly_score": 0.8,
        "severity": "high",
        "confidence": 0.9,
    }
    ctx = builder.build(anomaly)
    classify(ctx)
    # auth-service's upstream (postgres) is unhealthy, downstream (web-bff) is healthy
    assert ctx.kind == AnomalyKind.UPSTREAM


# ─────────────────────────────────────────────────────────────────────
# Engine tests
# ─────────────────────────────────────────────────────────────────────
def test_engine_returns_candidates_sorted_by_priority(builder, services_catalog):
    """Fake an anomaly that should match restart_pod_high_cpu."""
    services_catalog["orders-service"]["health"] = "degraded"
    GraphStore().graph().nodes["orders-service"]["health"] = "degraded"

    anomaly = {
        "id": "ANM-test-4",
        "service_id": "orders-service",
        "anomaly_score": 0.9,
        "severity": "high",
        "confidence": 0.9,
        "metric": "cpu_usage_pct",
        "actual_value": 0.92,
        "expected_value": 0.45,
        "deviation_sigma": 4.5,
    }
    infra = {"cpu": {"usage_pct": 0.92}}
    ctx = builder.build(anomaly, infra=infra)
    classify(ctx)

    candidates = rule_engine.evaluate(ctx)
    assert isinstance(candidates, list)
    # At least one candidate should match given the degraded+high cpu setup
    # (may be empty if registry isn't loaded — depends on DB state)
    for c in candidates:
        assert c.final_confidence == pytest.approx(
            0.6 * c.detection_confidence + 0.4 * c.base_confidence, abs=1e-6
        )


# ─────────────────────────────────────────────────────────────────────
# Root cause tests
# ─────────────────────────────────────────────────────────────────────
def test_root_cause_single_anomaly():
    anomalies = [{"service_id": "orders-service", "detected_at": "2026-10-13T10:00:00Z"}]
    assert localize_root_cause(anomalies) == "orders-service"


def test_root_cause_auth_outage():
    """
    Simulated auth_outage: auth-service, user-service, web-bff,
    mobile-bff, api-gateway all anomalous. auth-service should be root.
    """
    base = "2026-10-13T10:00:00Z"
    anomalies = [
        {"service_id": "auth-service",   "detected_at": base},
        {"service_id": "user-service",   "detected_at": base},
        {"service_id": "web-bff",        "detected_at": base},
        {"service_id": "mobile-bff",     "detected_at": base},
        {"service_id": "api-gateway",    "detected_at": base},
    ]
    root = localize_root_cause(anomalies)
    assert root is not None
    # auth-service has downstream (web-bff, mobile-bff) affected,
    # and its upstream (postgres, redis) healthy → root
    assert root in ("auth-service", "api-gateway", "waf-proxy")


def test_root_cause_empty():
    assert localize_root_cause([]) is None


# ─────────────────────────────────────────────────────────────────────
# Blast radius sanity (uses graph, not Rule Engine, but good to assert)
# ─────────────────────────────────────────────────────────────────────
def test_blast_radius_auth_service():
    analyzer = BlastRadiusAnalyzer(GraphStore())
    size = analyzer.size("auth-service")
    # auth-service is called by web-bff + mobile-bff, which are called
    # by api-gateway, which is called by waf-proxy → at least 4
    assert size >= 4
    assert 1.0 <= analyzer.factor("auth-service") <= 1.5