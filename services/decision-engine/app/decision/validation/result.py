# services/decision-engine/app/decision/validation/result.py
"""
ValidationResult — the single object that flows out of the Validation Layer.

Every field is auditable from `decision_log.context` — the orchestrator
serializes this verbatim into the JSONB `context` column, and every
sub-reason ("why did we shadow?", "why did we block?") is preserved.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.decision.models import PolicyOutcome
from app.rules.models import RiskLevel


@dataclass
class ConfidenceBreakdown:
    """Every number that fed the final confidence."""
    detection: float
    rule_base: float
    blended: float                        # 0.6*det + 0.4*base (from RuleCandidate)
    graph_certainty: float                # [0,1] — 1 = graph data is fresh/complete
    effective: float                      # blended * graph_certainty
    band: str                             # "LOW" | "MEDIUM" | "HIGH"

    def to_dict(self) -> dict[str, Any]:
        return {
            "detection": round(self.detection, 4),
            "rule_base": round(self.rule_base, 4),
            "blended": round(self.blended, 4),
            "graph_certainty": round(self.graph_certainty, 4),
            "effective": round(self.effective, 4),
            "band": self.band,
        }


@dataclass
class ConflictReport:
    """What the conflict detector found (empty = no conflict)."""
    has_conflict: bool = False
    kind: str | None = None               # "IN_FLIGHT" | "DEPENDENCY" | "REPEAT_FAILURE"
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_conflict": self.has_conflict,
            "kind": self.kind,
            "details": list(self.details),
        }


@dataclass
class ValidationResult:
    """
    Everything the Validation Layer decided for one RecoveryAction.

    `outcome` is the verdict; `reason` is the human one-liner;
    `detail` is the full machine-readable trace stored in decision_log.
    """
    outcome: PolicyOutcome
    reason: str

    confidence: ConfidenceBreakdown
    risk: RiskLevel
    conflict: ConflictReport

    # Optional — populated only when outcome == SHADOW_MODE
    shadow_payload: dict[str, Any] | None = None

    # Optional — populated when outcome == HUMAN_LOOP
    escalation_payload: dict[str, Any] | None = None

    # bookkeeping
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "reason": self.reason,
            "confidence": self.confidence.to_dict(),
            "risk": self.risk.value,
            "conflict": self.conflict.to_dict(),
            "shadow_payload": self.shadow_payload,
            "escalation_payload": self.escalation_payload,
            "validated_at": self.validated_at.isoformat(),
        }