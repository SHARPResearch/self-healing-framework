"""
Action Selector — Strategy: priority_then_confidence.

Given a list of RuleCandidates, pick the ONE that should proceed to
the Validation Layer.

Selection strategy (Option 1):
    1. Sort by priority DESC
    2. Tie-break by final_confidence DESC
    3. Pick #1
    4. Every other candidate is recorded as "rejected" with a reason

This is deterministic, auditable, and matches the YAML `priority` field
in the rule definitions.
"""
from __future__ import annotations

import logging

from app.decision.models import (
    ActionSelection,
    RejectedCandidate,
)
from app.rules.models import RuleCandidate

log = logging.getLogger(__name__)


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