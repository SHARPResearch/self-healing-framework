"""
Tests for Severity Calculator and Action Selector.

Run:
    uv run pytest tests/test_severity_action.py -v
"""
import pytest

from app.decision.severity import compute_severity
from app.decision.action_selector import select_action
from app.rules.models import (
    ActionType, RiskLevel, RuleCandidate, RuleGuardrail,
)


# ─────────────────────────────────────────────────────────────────────
# Severity
# ─────────────────────────────────────────────────────────────────────
class TestSeverity:
    def test_high_central_high_blast(self):
        """Worst case: 0.9 × 2.0 × 1.5 = 2.7 → CRITICAL"""
        sev = compute_severity(
            {"severity": "high"}, centrality=2.0, blast_factor=1.5
        )
        assert sev.base_severity == 0.9
        assert sev.centrality == 2.0
        assert sev.blast_factor == 1.5
        assert sev.effective_severity == pytest.approx(2.7, abs=1e-3)
        assert sev.normalized == pytest.approx(1.0, abs=1e-3)
        assert sev.label == "CRITICAL"

    def test_low_central_low_blast(self):
        """Best case: 0.3 × 1.0 × 1.0 = 0.3 → LOW"""
        sev = compute_severity(
            {"severity": "low"}, centrality=1.0, blast_factor=1.0
        )
        assert sev.effective_severity == pytest.approx(0.3, abs=1e-3)
        assert sev.normalized == pytest.approx(0.3 / 2.7, abs=1e-3)
        assert sev.label == "LOW"

    def test_medium_auth_like(self):
        """Realistic: high 0.9 × centrality 1.72 × blast 1.35 = ~2.09"""
        sev = compute_severity(
            {"severity": "high"}, centrality=1.72, blast_factor=1.35
        )
        assert sev.effective_severity == pytest.approx(2.0898, abs=1e-2)
        assert sev.label == "CRITICAL"

    def test_missing_severity(self):
        """Missing severity → default low (0.3)"""
        sev = compute_severity({}, centrality=1.0, blast_factor=1.0)
        assert sev.base_severity == 0.3

    def test_clamped_centrality(self):
        """Centrality > 2.0 should be clamped."""
        sev = compute_severity(
            {"severity": "high"}, centrality=3.5, blast_factor=1.0
        )
        assert sev.centrality == 2.0

    def test_clamped_blast_factor(self):
        """Blast factor > 1.5 should be clamped."""
        sev = compute_severity(
            {"severity": "high"}, centrality=1.0, blast_factor=2.0
        )
        assert sev.blast_factor == 1.5


# ─────────────────────────────────────────────────────────────────────
# Action Selector
# ─────────────────────────────────────────────────────────────────────
def _cand(rule_id: str, priority: int, conf: float, action=ActionType.RESTART_POD):
    return RuleCandidate(
        rule_id=rule_id,
        rule_version=1,
        priority=priority,
        action=action,
        params={},
        base_confidence=0.8,
        detection_confidence=0.9,
        final_confidence=conf,
        base_risk=RiskLevel.MEDIUM,
        blast_factor=1.2,
        centrality=1.5,
        guardrails=RuleGuardrail(),
    )


class TestActionSelector:
    def test_empty(self):
        assert select_action([]) is None

    def test_single(self):
        sel = select_action([_cand("r1", 100, 0.83)])
        assert sel is not None
        assert sel.selected["rule_id"] == "r1"
        assert sel.rejected == []

    def test_priority_wins(self):
        """Higher priority wins even with lower confidence."""
        c1 = _cand("r-low", priority=80, conf=0.90)
        c2 = _cand("r-high", priority=100, conf=0.75)
        sel = select_action([c1, c2])
        assert sel.selected["rule_id"] == "r-high"
        assert len(sel.rejected) == 1
        assert sel.rejected[0].rule_id == "r-low"
        assert "priority" in sel.rejected[0].reason.lower()

    def test_confidence_tiebreak(self):
        """Same priority → higher confidence wins."""
        c1 = _cand("r-a", priority=100, conf=0.78)
        c2 = _cand("r-b", priority=100, conf=0.83)
        sel = select_action([c1, c2])
        assert sel.selected["rule_id"] == "r-b"
        assert "confidence" in sel.rejected[0].reason.lower()

    def test_three_candidates(self):
        """Your example: restart, scale, circuit."""
        c1 = _cand("restart", priority=100, conf=0.83, action=ActionType.RESTART_POD)
        c2 = _cand("scale", priority=95, conf=0.78, action=ActionType.SCALE_UP)
        c3 = _cand("circuit", priority=110, conf=0.82, action=ActionType.OPEN_CIRCUIT)
        sel = select_action([c1, c2, c3])
        assert sel.selected["rule_id"] == "circuit"  # highest priority
        assert len(sel.rejected) == 2
        rejected_ids = {r.rule_id for r in sel.rejected}
        assert rejected_ids == {"restart", "scale"}

    def test_deterministic_order(self):
        """Same inputs → same winner every time."""
        cs = [_cand(f"r{i}", 100, 0.80) for i in range(5)]
        winners = {select_action(cs).selected["rule_id"] for _ in range(10)}
        assert len(winners) == 1  # always the same winner