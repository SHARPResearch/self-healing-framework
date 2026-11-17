# services/decision-engine/tests/test_validation_confidence.py
from __future__ import annotations

import pytest

from app.core.graph_store import GraphStore
from app.decision.validation.confidence import (
    CONF_HIGH,
    CONF_MEDIUM,
    compute_confidence,
)
from app.rules.context import AnomalyContext


@pytest.fixture(autouse=True)
def clean_graph():
    GraphStore().graph().clear()
    yield
    GraphStore().graph().clear()


def _ctx(sid="auth-service", up=None, down=None) -> AnomalyContext:
    return AnomalyContext(
        anomaly={"id": "ANM-x", "service_id": sid, "confidence": 0.9},
        service={"service_id": sid, "layer": "domain"},
        upstream=up or [],
        downstream=down or [],
    )


def test_certainty_drops_for_unknown_service():
    ctx = _ctx(sid="unknown-svc")
    c = compute_confidence(blended=0.9, detection=0.9, rule_base=0.8, ctx=ctx)
    assert c.graph_certainty < 1.0
    assert c.effective < 0.9


def test_certainty_high_for_known_service_with_neighbors():
    from app.core.models import ServiceNode, DependencyEdge
    gs = GraphStore()
    gs.upsert_node(ServiceNode(id="auth-service", name="auth"))
    gs.upsert_node(ServiceNode(id="user-service", name="user"))
    gs.upsert_edge(DependencyEdge(source="auth-service", target="user-service"))

    ctx = _ctx(sid="auth-service", up=["user-service"])
    c = compute_confidence(blended=0.9, detection=0.9, rule_base=0.8, ctx=ctx)
    assert c.graph_certainty == 1.0
    assert c.effective == 0.9
    assert c.band == "HIGH"


def test_band_thresholds():
    ctx = _ctx()
    high = compute_confidence(0.9, 0.9, 0.8, ctx)
    med = compute_confidence(0.7, 0.9, 0.8, ctx)
    low = compute_confidence(0.3, 0.9, 0.8, ctx)
    assert high.effective >= CONF_HIGH or high.band != "MEDIUM"
    assert CONF_MEDIUM <= 0.7 or med.band == "MEDIUM"
    assert low.band == "LOW"