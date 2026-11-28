"""
test_hybrid_arbitration.py
Tests to prove Traffic Cop correctly enforces the Decision Policy Matrix.
"""
from app.hybrid_arbitration import HybridArbitrator, PolicyOutcome, SeverityLevel

def test_arbitration_safety_veto():
    """RL cannot override a BLOCK or HUMAN_LOOP from the Rule Engine."""
    arbitrator = HybridArbitrator()
    result = arbitrator.decide(
        rule_action="RESTART_POD", rule_confidence=0.9, rule_outcome=PolicyOutcome.BLOCK,
        rl_action="SCALE_UP", rl_confidence=0.95, severity=SeverityLevel.MEDIUM
    )
    assert result["winning_engine"] == "RULE_ENGINE"
    assert "Safety veto" in result["reason"]

def test_arbitration_high_severity_goes_to_rule():
    """High severity scenarios must always use the deterministic Rule Engine."""
    arbitrator = HybridArbitrator()
    result = arbitrator.decide(
        rule_action="RESTART_POD", rule_confidence=0.9, rule_outcome=PolicyOutcome.AUTO_EXECUTE,
        rl_action="SCALE_UP", rl_confidence=0.95, severity=SeverityLevel.HIGH
    )
    assert result["winning_engine"] == "RULE_ENGINE"
    assert "Time-critical" in result["reason"]

def test_arbitration_rl_wins_on_medium_severity():
    """RL Engine should win on Medium severity if both are confident."""
    arbitrator = HybridArbitrator()
    result = arbitrator.decide(
        rule_action="RESTART_POD", rule_confidence=0.8, rule_outcome=PolicyOutcome.AUTO_EXECUTE,
        rl_action="SCALE_UP", rl_confidence=0.85, severity=SeverityLevel.MEDIUM
    )
    assert result["winning_engine"] == "RL_ENGINE"
    assert "Adaptive signal" in result["reason"]

def test_arbitration_rl_uncertainty_fallback():
    """If RL confidence is low, it must fall back to the Rule Engine."""
    arbitrator = HybridArbitrator()
    result = arbitrator.decide(
        rule_action="RESTART_POD", rule_confidence=0.8, rule_outcome=PolicyOutcome.AUTO_EXECUTE,
        rl_action="SCALE_UP", rl_confidence=0.40, severity=SeverityLevel.MEDIUM
    )
    assert result["winning_engine"] == "RULE_ENGINE"
    assert "RL uncertain" in result["reason"]