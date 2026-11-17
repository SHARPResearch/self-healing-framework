# services/decision-engine/tests/test_validation_shadow.py
from __future__ import annotations

from app.decision.validation.result import ConfidenceBreakdown
from app.decision.validation.shadow import (
    build_shadow_payload,
    observe_shadow_outcome,
)
from app.rules.context import AnomalyContext
from app.rules.models import ActionType, RiskLevel


def _ctx():
    return AnomalyContext(
        anomaly={"id": "ANM-x", "service_id": "payment-svc", "anomaly_score": 0.72},
        service={"service_id": "payment-svc"},
    )


def _conf():
    return ConfidenceBreakdown(
        detection=0.9, rule_base=0.8, blended=0.85,
        graph_certainty=1.0, effective=0.71, band="MEDIUM",
    )


def test_shadow_payload_has_doc_shape():
    p = build_shadow_payload(
        decision_id="DEC-1",
        anomaly_id="ANM-x",
        ctx=_ctx(),
        action=ActionType.RESTART_POD,
        confidence=_conf(),
        risk=RiskLevel.MEDIUM,
    )
    for key in (
        "SHADOW_ID", "SERVICE", "ANOMALY_SCORE", "CANDIDATE_ACTION",
        "CONFIDENCE", "RISK", "POLICY_OUTCOME", "SIMULATED_OUTCOME",
        "ACTUAL_OUTCOME", "VERDICT", "LEARNING",
    ):
        assert key in p
    assert p["POLICY_OUTCOME"] == "SHADOW_MODE"
    assert p["SIMULATED_OUTCOME"]["EXPECTED_ANOMALY_DROP"] > 0
    assert p["ACTUAL_OUTCOME"] is None


def test_observe_unnecessary_verdict():
    p = build_shadow_payload(
        decision_id="DEC-1", anomaly_id="ANM-x", ctx=_ctx(),
        action=ActionType.RESTART_POD, confidence=_conf(),
        risk=RiskLevel.MEDIUM,
    )
    updated = observe_shadow_outcome(p, resolved_naturally=True, resolution_time_sec=50)
    assert updated["VERDICT"] == "ACTION_WOULD_HAVE_BEEN_UNNECESSARY"
    assert "reduce weight" in updated["LEARNING"]


def test_observe_helpful_verdict_when_not_resolved():
    p = build_shadow_payload(
        decision_id="DEC-1", anomaly_id="ANM-x", ctx=_ctx(),
        action=ActionType.RESTART_POD, confidence=_conf(),
        risk=RiskLevel.MEDIUM,
    )
    updated = observe_shadow_outcome(p, resolved_naturally=False, resolution_time_sec=999)
    assert updated["VERDICT"] == "ACTION_WOULD_HAVE_HELPED"