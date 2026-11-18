# services/decision-engine/tests/test_validation_policy.py
from __future__ import annotations

from app.decision.models import PolicyOutcome
from app.decision.validation.policy_matrix import decide_outcome
from app.decision.validation.result import ConfidenceBreakdown, ConflictReport
from app.rules.models import RiskLevel


def _conf(band: str, effective: float = 0.9) -> ConfidenceBreakdown:
    return ConfidenceBreakdown(
        detection=0.9, rule_base=0.8, blended=0.9,
        graph_certainty=1.0, effective=effective, band=band,
    )


def test_conflict_blocks():
    out, _ = decide_outcome(
        _conf("HIGH"), RiskLevel.LOW,
        ConflictReport(has_conflict=True, kind="IN_FLIGHT", details=["x"]),
    )
    assert out == PolicyOutcome.BLOCK


def test_high_risk_escalates():
    out, _ = decide_outcome(_conf("HIGH"), RiskLevel.HIGH, ConflictReport())
    assert out == PolicyOutcome.HUMAN_LOOP


def test_low_confidence_blocks():
    out, _ = decide_outcome(_conf("LOW", 0.4), RiskLevel.LOW, ConflictReport())
    assert out == PolicyOutcome.BLOCK


def test_high_conf_low_risk_auto():
    out, _ = decide_outcome(_conf("HIGH"), RiskLevel.LOW, ConflictReport())
    assert out == PolicyOutcome.AUTO_EXECUTE


def test_medium_conf_shadows():
    out, _ = decide_outcome(_conf("MEDIUM", 0.7), RiskLevel.LOW, ConflictReport())
    assert out == PolicyOutcome.SHADOW_MODE


def test_high_conf_medium_risk_shadows():
    out, _ = decide_outcome(_conf("HIGH"), RiskLevel.MEDIUM, ConflictReport())
    assert out == PolicyOutcome.SHADOW_MODE