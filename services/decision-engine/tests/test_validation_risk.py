# services/decision-engine/tests/test_validation_risk.py
from __future__ import annotations

from app.decision.blast_analysis import BlastRadiusAnalysis
from app.decision.validation.risk_classifier import classify_risk
from app.rules.models import ActionType, RiskLevel


def _blast(rec: RiskLevel, size=0) -> BlastRadiusAnalysis:
    return BlastRadiusAnalysis(
        service_id="svc", action=ActionType.RESTART_POD,
        size=size, factor=1.0, weighted=float(size),
        recommended_risk=rec,
    )


def test_takes_the_worse():
    risk, _ = classify_risk(RiskLevel.LOW, _blast(RiskLevel.HIGH))
    assert risk == RiskLevel.HIGH

    risk, _ = classify_risk(RiskLevel.HIGH, _blast(RiskLevel.LOW))
    assert risk == RiskLevel.HIGH


def test_repeat_failure_bumps_to_high():
    risk, reason = classify_risk(
        RiskLevel.MEDIUM, _blast(RiskLevel.MEDIUM), repeat_failure_count=3,
    )
    assert risk == RiskLevel.HIGH
    assert "repeat-failure" in reason.lower()


def test_no_bump_below_threshold():
    risk, _ = classify_risk(
        RiskLevel.MEDIUM, _blast(RiskLevel.LOW), repeat_failure_count=1,
    )
    assert risk == RiskLevel.MEDIUM