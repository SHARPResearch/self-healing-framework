# services/decision-engine/tests/test_validation_orchestrator.py
"""
End-to-end test of validator.validate() with a fake Postgres store
(no live DB required).
"""
from __future__ import annotations

import pytest

from app.core.graph_store import GraphStore
from app.decision.action_selector import RecoveryAction
from app.decision.blast_analysis import BlastRadiusAnalysis
from app.decision.models import PolicyOutcome
from app.decision.validation.validator import validate
from app.rules.context import AnomalyContext
from app.rules.models import ActionType, RiskLevel


@pytest.fixture(autouse=True)
def clean_graph():
    from app.core.models import DependencyEdge, ServiceNode

    store = GraphStore()
    store.graph().clear()
    store.upsert_node(ServiceNode(id="auth-service", name="auth"))
    store.upsert_node(ServiceNode(id="user-service", name="user"))
    store.upsert_edge(DependencyEdge(source="auth-service", target="user-service"))
    yield
    store.graph().clear()


class FakeStore:
    async def list_in_flight(self, service_id):
        return []

    async def list_in_flight_multi(self, service_ids):
        return []

    async def count_recent_failures(self, service_id, action, window_min=30):
        return 0


@pytest.fixture
def patch_store(monkeypatch):
    import app.persistence.postgres as pg
    monkeypatch.setattr(pg, "postgres_store", FakeStore())
    # Also patch the module-level import in validator (it imports inside the fn)


def _ctx(sid="auth-service") -> AnomalyContext:
    return AnomalyContext(
        anomaly={"id": "ANM-x", "service_id": sid, "confidence": 0.92, "anomaly_score": 0.9},
        service={"service_id": sid, "layer": "domain"},
        upstream=["user-service"],
    )


def _recovery(
    action=ActionType.RESTART_POD,
    base_risk=RiskLevel.LOW,
    confidence=0.9,
    blast_risk=RiskLevel.LOW,
) -> RecoveryAction:
    return RecoveryAction(
        rule_id="restart_pod_high_cpu", rule_version=1,
        action=action, params={}, service_id="auth-service",
        confidence=confidence, base_risk=base_risk,
        blast=BlastRadiusAnalysis(
            service_id="auth-service", action=action,
            size=0, factor=1.0, weighted=0.0,
            recommended_risk=blast_risk,
            is_leaf=True,
        ),
    )


@pytest.mark.asyncio
async def test_auto_execute_path(patch_store):
    result = await validate(_recovery(), _ctx())
    assert result.outcome == PolicyOutcome.AUTO_EXECUTE
    assert result.shadow_payload is None
    assert result.escalation_payload is None


@pytest.mark.asyncio
async def test_shadow_path(patch_store):
    result = await validate(_recovery(confidence=0.70), _ctx())
    assert result.outcome == PolicyOutcome.SHADOW_MODE
    assert result.shadow_payload is not None
    assert result.shadow_payload["POLICY_OUTCOME"] == "SHADOW_MODE"


@pytest.mark.asyncio
async def test_human_loop_path(patch_store):
    result = await validate(_recovery(blast_risk=RiskLevel.HIGH), _ctx())
    assert result.outcome == PolicyOutcome.HUMAN_LOOP
    assert result.escalation_payload is not None
    assert result.escalation_payload["risk"] == "HIGH"


@pytest.mark.asyncio
async def test_block_on_low_confidence(patch_store):
    result = await validate(_recovery(confidence=0.30), _ctx())
    assert result.outcome == PolicyOutcome.BLOCK


@pytest.mark.asyncio
async def test_conflict_overrides_everything(patch_store, monkeypatch):
    import app.persistence.postgres as pg

    class ConflictStore(FakeStore):
        async def list_in_flight(self, service_id):
            from datetime import datetime, timedelta, timezone
            return [{
                "decision_id": "DEC-old",
                "service_id": service_id,
                "action": "SCALE_UP",
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            }]

    monkeypatch.setattr(pg, "postgres_store", ConflictStore())
    result = await validate(_recovery(confidence=0.99), _ctx())
    assert result.outcome == PolicyOutcome.BLOCK
    assert result.conflict.has_conflict is True
    assert result.conflict.kind == "IN_FLIGHT"