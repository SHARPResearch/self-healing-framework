# self-healing-framework\services\decision-engine\app\decision\action_selector.py
"""
# ─────────────────────────────────────────────────────────────────────
# Phase 1 additions — RecoveryAction envelope + blast-radius enrichment
#
# The existing `select_action()` returns an `ActionSelection` (the winning
# RuleCandidate + rejection reasons). That contract is unchanged.
#
# The two helpers below build on top of it without touching it:
#
#   select_recovery_action() — wraps a RuleCandidate in a RecoveryAction
#                              (action + params + blast analysis + hint)
#   enrich_with_blast()       — adds BlastRadiusAnalysis to a selection
# ─────────────────────────────────────────────────────────────────────

"""
from __future__ import annotations

import logging

from app.decision.models import (
    ActionSelection,
    RejectedCandidate,
)
from app.rules.models import RuleCandidate
from dataclasses import dataclass, field
from typing import Any

from app.decision.blast_analysis import (
    BlastRadiusAnalysis,
    BlastRadiusAnalyzerDecision,
    blast_analysis as _blast_analysis_singleton,
)
from app.rules.models import ActionType, RiskLevel, RuleCandidate

log = logging.getLogger(__name__)
@dataclass
class RecoveryAction:
    """
    The thing that flows to the Validation Layer.

    A `RuleCandidate` says *what rule matched*.
    A `RecoveryAction` says *what to do, how big the blast is, and how risky*.
    """
    rule_id: str
    rule_version: int
    action: ActionType
    params: dict[str, Any]
    service_id: str
    confidence: float                     # blended (0.6*det + 0.4*base)
    base_risk: RiskLevel                  # from the rule definition
    blast: BlastRadiusAnalysis            # decision-facing blast-radius view
    guardrails: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

    @property
    def effective_risk(self) -> RiskLevel:
        """The worse of (rule base_risk, blast recommendation)."""
        order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
        base = order.get(self.base_risk, 1)
        blast = order.get(self.blast.recommended_risk, 1)
        worst = max(base, blast)
        for lvl, n in order.items():
            if n == worst:
                return lvl
        return RiskLevel.MEDIUM

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "action": self.action.value,
            "params": self.params,
            "service_id": self.service_id,
            "confidence": round(self.confidence, 4),
            "base_risk": self.base_risk.value,
            "effective_risk": self.effective_risk.value,
            "blast": self.blast.to_dict(),
            "guardrails": self.guardrails,
            "rationale": self.rationale,
        }


def select_action(candidates: list[RuleCandidate]) -> ActionSelection | None:
    """
    Pick the best candidate. Returns None if candidates is empty.
    """
    if not candidates:
        return None

    # Sort by priority DESC, then final_confidence DESC (matches RuleEngine order)
    ranked = sorted(
        candidates,
        key=lambda c: (-c.priority, -c.final_confidence, c.rule_id),
    )
    winner = ranked[0]

    rejected = [
        RejectedCandidate(
            rule_id=c.rule_id,
            action=c.action,
            priority=c.priority,
            final_confidence=c.final_confidence,
            reason=_reject_reason(c, winner),
        )
        for c in ranked[1:]
    ]

    reason = (
        f"highest priority ({winner.priority})"
        if len(ranked) == 1 or ranked[1].priority < winner.priority
        else f"highest priority and confidence (tie at priority {winner.priority})"
    )

    return ActionSelection(
        selected=winner.model_dump(mode="json"),
        rejected=rejected,
        strategy="priority_then_confidence",
        reason=reason,
    )


def _reject_reason(c: RuleCandidate, winner: RuleCandidate) -> str:
    if c.priority < winner.priority:
        return f"lower priority ({c.priority} < {winner.priority})"
    if c.priority == winner.priority:
        return (
            f"tied priority; lower confidence "
            f"({c.final_confidence:.3f} < {winner.final_confidence:.3f})"
        )
    return "superseded"




def select_recovery_action(
    candidates: list[RuleCandidate],
    service_id: str,
    *,
    analyzer: BlastRadiusAnalyzerDecision | None = None,
    criticality: dict[str, float] | None = None,
) -> RecoveryAction | None:
    """
    Pick the winner via `select_action()`, then enrich it with a
    decision-facing blast-radius analysis.

    Returns None if candidates is empty.
    """
    selection = select_action(candidates)
    if selection is None:
        return None

    winner_dict = selection.selected
    action = ActionType(winner_dict["action"])

    a = analyzer or _blast_analysis_singleton
    blast = a.analyze(service_id, action, criticality)

    return RecoveryAction(
        rule_id=winner_dict["rule_id"],
        rule_version=int(winner_dict.get("rule_version", 1)),
        action=action,
        params=winner_dict.get("params") or {},
        service_id=service_id,
        confidence=float(winner_dict.get("final_confidence", 0.0)),
        base_risk=RiskLevel(winner_dict.get("base_risk", "MEDIUM")),
        blast=blast,
        guardrails=winner_dict.get("guardrails") or {},
        rationale=f"selected by {selection.strategy}: {selection.reason}",
    )


def enrich_with_blast(
    candidate: RuleCandidate,
    service_id: str,
    *,
    analyzer: BlastRadiusAnalyzerDecision | None = None,
    criticality: dict[str, float] | None = None,
) -> RecoveryAction:
    """
    Single-candidate variant — useful when you already know the winner
    (e.g. from `rule_engine.evaluate_best()`).
    """
    a = analyzer or _blast_analysis_singleton
    blast = a.analyze(service_id, candidate.action, criticality)
    return RecoveryAction(
        rule_id=candidate.rule_id,
        rule_version=candidate.rule_version,
        action=candidate.action,
        params=dict(candidate.params),
        service_id=service_id,
        confidence=float(candidate.final_confidence),
        base_risk=candidate.base_risk,
        blast=blast,
        guardrails=candidate.guardrails.model_dump() if hasattr(candidate.guardrails, "model_dump") else {},
        rationale="single-candidate selection",
    )