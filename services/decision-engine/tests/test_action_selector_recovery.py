# services/decision-engine/tests/test_action_selector_recovery.py
"""
Tests for the Phase-1 additions to action_selector:
    - select_recovery_action()
    - enrich_with_blast()
    - RecoveryAction.effective_risk

The existing `select_action()` contract is exercised by
tests/test_rule_engine.py — we don't duplicate that here.
"""
from __future__ import annotations

import pytest

from app.core.graph_store import GraphStore
from app.decision.action_selector import (
    RecoveryAction,
    enrich_with_blast,
    select_recovery_action,
)
from app.decision.blast_analysis import BlastRadiusAnalyzerDecision
from app.rules.models import (
    ActionType,
    RiskLevel,
    RuleCandidate,
    RuleGuardrail,
)


@pytest.fixture(autouse=True)
def clean_graph():
    GraphStore().graph().clear()
    yield
    GraphStore().graph().clear()


def _cand(
    *,
    rule_id="restart_pod_high_cpu",
    priority=100,
    action=ActionType.RESTART_POD,
    base_risk=RiskLevel.MEDIUM,
    base_conf=0.85,
    det_conf=0.92,
) -> RuleCandidate:
    return RuleCandidate(
        rule_id=rule_id,
        rule_version=1,
        priority=priority,
        action=action,
        params={"grace_period_sec": 30},
        base_confidence=base_conf,
        detection_confidence=det_conf,
        final_confidence=RuleCandidate.blend(det_conf, base_conf),
        base_risk=base_risk,
        blast_factor=1.0,
        centrality=1.0,
        guardrails=RuleGuardrail(cooldown_seconds=300, max_per_hour=3),
    )


# ─────────────────────────────────────────────────────────────────────
# select_recovery_action
# ─────────────────────────────────────────────────────────────────────
def test_select_recovery_action_returns_none_for_empty():
    assert select_recovery_action([], "auth-service") is None


def test_select_recovery_action_picks_winner_and_adds_blast():
    candidates = [
        _cand(rule_id="lo", priority=50),
        _cand(rule_id="hi", priority=200),
    ]
    a = BlastRadiusAnalyzerDecision()
    result = select_recovery_action(candidates, "auth-service", analyzer=a)

    assert result is not None
    assert result.rule_id == "hi"            # winner
    assert result.action == ActionType.RESTART_POD
    assert result.service_id == "auth-service"
    assert result.blast.service_id == "auth-service"
    assert isinstance(result.blast.recommended_risk, RiskLevel)


def test_select_recovery_action_preserves_params_and_guardrails():
    candidates = [_cand()]
    result = select_recovery_action(candidates, "auth-service")
    assert result is not None
    assert result.params == {"grace_period_sec": 30}
    assert result.guardrails["cooldown_seconds"] == 300


# ─────────────────────────────────────────────────────────────────────
# effective_risk = worse of (base_risk, blast.recommended_risk)
# ─────────────────────────────────────────────────────────────────────
def test_effective_risk_takes_the_worse():
    from app.decision.blast_analysis import BlastRadiusAnalysis

    ra = RecoveryAction(
        rule_id="x", rule_version=1,
        action=ActionType.SCALE_UP, params={},
        service_id="svc", confidence=0.9,
        base_risk=RiskLevel.LOW,
        blast=BlastRadiusAnalysis(
            service_id="svc", action=ActionType.SCALE_UP,
            size=10, factor=1.5, weighted=10.0,
            recommended_risk=RiskLevel.HIGH,
        ),
    )
    assert ra.effective_risk == RiskLevel.HIGH


def test_effective_risk_when_base_is_worse():
    from app.decision.blast_analysis import BlastRadiusAnalysis

    ra = RecoveryAction(
        rule_id="x", rule_version=1,
        action=ActionType.SCALE_UP, params={},
        service_id="svc", confidence=0.9,
        base_risk=RiskLevel.HIGH,
        blast=BlastRadiusAnalysis(
            service_id="svc", action=ActionType.SCALE_UP,
            size=0, factor=1.0, weighted=0.0,
            recommended_risk=RiskLevel.LOW,
        ),
    )
    assert ra.effective_risk == RiskLevel.HIGH


# ─────────────────────────────────────────────────────────────────────
# enrich_with_blast
# ─────────────────────────────────────────────────────────────────────
def test_enrich_with_blast_for_single_candidate():
    c = _cand(rule_id="solo", base_risk=RiskLevel.LOW)
    result = enrich_with_blast(c, "auth-service")
    assert result.rule_id == "solo"
    assert result.confidence == c.final_confidence
    assert result.blast.service_id == "auth-service"