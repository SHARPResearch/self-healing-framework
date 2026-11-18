# services/decision-engine/app/decision/guardrails/verdict.py
"""
GuardrailVerdict — the single object returned by `guardrails.check()`.

Unlike the Validation Layer (which returns one of four PolicyOutcomes),
guardrails are binary: PASS or BLOCK. Each guardrail contributes a
sub-verdict with a `blocked` flag and a `reason`.

The orchestrator (guardrails.py) returns PASS only when every sub-check
passes. When any sub-check blocks, the first blocker becomes `reason`
and `blocker` names which guardrail fired.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class GuardrailCheck:
    """One guardrail's verdict."""
    name: str                                   # "cooldown" | "action_counter" | "idempotency"
    blocked: bool
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "blocked": self.blocked,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass
class GuardrailVerdict:
    """Aggregate verdict — all checks that ran, and the overall result."""
    allowed: bool
    blocker: str | None                         # which guardrail blocked (None = allowed)
    reason: str
    checks: list[GuardrailCheck] = field(default_factory=list)
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "blocker": self.blocker,
            "reason": self.reason,
            "checks": [c.to_dict() for c in self.checks],
            "decided_at": self.decided_at.isoformat(),
        }


def allow(checks: list[GuardrailCheck]) -> GuardrailVerdict:
    return GuardrailVerdict(
        allowed=True,
        blocker=None,
        reason="all guardrails passed",
        checks=checks,
    )


def block(checks: list[GuardrailCheck], blocker: GuardrailCheck) -> GuardrailVerdict:
    return GuardrailVerdict(
        allowed=False,
        blocker=blocker.name,
        reason=blocker.reason,
        checks=checks,
    )