# services/decision-engine/tests/test_blast_analysis.py
"""
Tests for app.decision.blast_analysis.

These build a tiny in-memory DiGraph and verify the decision-facing
recommendation matches the design doc (Section 5.4):

    - Leaf + low-risk action         → LOW
    - Hub + non-trivial factor       → HIGH
    - Intrinsic-high action (ROLLBACK) → HIGH regardless of size
"""
from __future__ import annotations

import pytest

from app.core.blast_radius import BlastRadiusAnalyzer
from app.core.graph_store import GraphStore
from app.decision.blast_analysis import (
    BlastRadiusAnalyzerDecision,
    _ACTION_INTRINSIC_RISK,
)
from app.rules.models import ActionType, RiskLevel


@pytest.fixture
def empty_store(monkeypatch):
    """Fresh GraphStore with no nodes/edges."""
    from app.core import graph_store as gs_mod

    store = GraphStore()
    # Wipe — singleton may have state from other tests
    g = store.graph()
    g.clear()
    return store


def _add(store: GraphStore, caller: str, dependency: str, strength: float = 1.0):
    from app.core.models import ServiceNode, DependencyEdge
    for nid in (caller, dependency):
        if nid not in store.graph():
            store.upsert_node(ServiceNode(id=nid, name=nid, criticality=1.0))
    store.upsert_edge(DependencyEdge(source=caller, target=dependency, strength=strength))


# ─────────────────────────────────────────────────────────────────────
# Graph shapes
# ─────────────────────────────────────────────────────────────────────
def test_leaf_service_is_low_risk(empty_store):
    # notification-service → nothing depends on it
    from app.core.models import ServiceNode
    empty_store.upsert_node(ServiceNode(id="notification-service", name="notif"))

    a = BlastRadiusAnalyzerDecision(empty_store)
    result = a.analyze("notification-service", ActionType.RESTART_POD)

    assert result.size == 0
    assert result.is_leaf is True
    assert result.recommended_risk == RiskLevel.LOW
    assert "leaf" in result.rationale.lower()


def test_hub_service_is_high_risk(empty_store):
    # 6 services all depend on postgres → postgres is a hub
    for i in range(6):
        _add(empty_store, f"svc-{i}", "postgres")

    a = BlastRadiusAnalyzerDecision(empty_store)
    result = a.analyze("postgres", ActionType.SCALE_UP)

    assert result.size == 6
    assert result.is_hub is True
    assert result.recommended_risk == RiskLevel.HIGH
    assert "hub" in result.rationale.lower()


def test_rollback_is_high_risk_everywhere(empty_store):
    # Even a leaf service — ROLLBACK is intrinsically high
    from app.core.models import ServiceNode
    empty_store.upsert_node(ServiceNode(id="leaf", name="leaf"))

    a = BlastRadiusAnalyzerDecision(empty_store)
    result = a.analyze("leaf", ActionType.ROLLBACK)

    assert result.recommended_risk == RiskLevel.HIGH
    assert "intrinsically high-risk" in result.rationale


def test_noop_has_zero_intrinsic_risk(empty_store):
    from app.core.models import ServiceNode
    empty_store.upsert_node(ServiceNode(id="leaf", name="leaf"))

    a = BlastRadiusAnalyzerDecision(empty_store)
    result = a.analyze("leaf", ActionType.NOOP)

    assert result.intrinsic_risk == _ACTION_INTRINSIC_RISK[ActionType.NOOP]
    assert result.recommended_risk == RiskLevel.LOW


def test_unknown_service_returns_empty(empty_store):
    a = BlastRadiusAnalyzerDecision(empty_store)
    result = a.analyze("does-not-exist", ActionType.RESTART_POD)

    assert result.size == 0
    assert result.members == []
    assert result.recommended_risk == RiskLevel.LOW


# ─────────────────────────────────────────────────────────────────────
# Serialization
# ─────────────────────────────────────────────────────────────────────
def test_to_dict_is_json_safe(empty_store):
    import json
    from app.core.models import ServiceNode

    empty_store.upsert_node(ServiceNode(id="solo", name="solo"))
    a = BlastRadiusAnalyzerDecision(empty_store)
    result = a.analyze("solo", ActionType.RESTART_POD)

    # Must not raise
    json.dumps(result.to_dict())