"""
Decision models.

SeverityBreakdown  — every component of the effective severity score
ActionSelection    — which candidate won + which were rejected + why
Decision           — the full record that flows to Validation → Execution → Log

The Decision object is what gets written to the `decision_log` table, so it
mirrors those columns exactly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.rules.models import ActionType, RiskLevel, RuleGuardrail


# ─────────────────────────────────────────────────────────────────────
# Policy outcome — used by the Validation Layer, defined here so that
# Decision can carry the field with a stable schema.
# ─────────────────────────────────────────────────────────────────────
class PolicyOutcome(str, Enum):
    AUTO_EXECUTE       = "AUTO_EXECUTE"        # confidence ≥ 0.85 AND risk = LOW
    SHADOW_MODE        = "SHADOW_MODE"         # 0.60 ≤ confidence < 0.85
    HUMAN_LOOP         = "HUMAN_LOOP"          # risk = HIGH or repeat-failure ≥ 2
    BLOCK              = "BLOCK"               # confidence < 0.60 or dependency conflict
    NO_RULE_MATCHED    = "NO_RULE_MATCHED"     # no rule matched (terminal — no retry)
    PENDING_VALIDATION = "PENDING_VALIDATION"  # reserved for future


# ─────────────────────────────────────────────────────────────────────
# Severity
# ─────────────────────────────────────────────────────────────────────
class SeverityBreakdown(BaseModel):
    """
    Every component of the effective severity, so the number is auditable.

    EFFECTIVE = BASE × CENTRALITY × BLAST_FACTOR
        BASE          ∈ {0.3, 0.6, 0.9}   from anomaly.severity label
        CENTRALITY    ∈ [1.0, 2.0]        from graph
        BLAST_FACTOR  ∈ [1.0, 1.5]        from graph

    Maximum possible = 0.9 × 2.0 × 1.5 = 2.7
    """
    base_severity: float = Field(..., ge=0.0, le=1.0)
    centrality: float = Field(..., ge=1.0, le=2.0)
    blast_factor: float = Field(..., ge=1.0, le=1.5)

    effective_severity: float = Field(..., ge=0.0, le=2.7)
    normalized: float = Field(..., ge=0.0, le=1.0)
    label: str = Field(..., description="LOW / MEDIUM / HIGH / CRITICAL")


# ─────────────────────────────────────────────────────────────────────
# Action selection
# ─────────────────────────────────────────────────────────────────────
class RejectedCandidate(BaseModel):
    """A rule that matched but was not selected. Kept for audit."""
    rule_id: str
    action: ActionType
    priority: int
    final_confidence: float
    reason: str = ""


class ActionSelection(BaseModel):
    """Output of the Action Selector."""
    selected: dict[str, Any] = Field(..., description="Winning RuleCandidate as dict")
    rejected: list[RejectedCandidate] = Field(default_factory=list)
    strategy: str = "priority_then_confidence"
    reason: str = ""


# ─────────────────────────────────────────────────────────────────────
# The Decision — the full record
# ─────────────────────────────────────────────────────────────────────
class Decision(BaseModel):
    """
    Full decision object. Fed to Validation Layer, then Execution, then Log.

    Every field here either:
      (a) is needed by the Validation Layer, or
      (b) is stored in decision_log (see schemas.py)
    """
    # identity
    decision_id: str = Field(..., description="DEC-{timestamp}-{random}")
    anomaly_id: str
    service_id: str

    # rule origin
    rule_id: str
    rule_version: int

    # action
    action: ActionType
    action_params: dict[str, Any] = Field(default_factory=dict)

    # confidence (three numbers — all stored)
    detection_conf: float = Field(..., ge=0.0, le=1.0)
    rule_conf: float = Field(..., ge=0.0, le=1.0)
    final_conf: float = Field(..., ge=0.0, le=1.0)

    # severity (four numbers — all stored)
    severity: SeverityBreakdown

    # risk classification
    base_risk: RiskLevel
    blast_factor: float = Field(..., ge=1.0, le=1.5)
    centrality: float = Field(..., ge=1.0, le=2.0)

    # guardrails carried over from rule
    guardrails: RuleGuardrail = Field(default_factory=RuleGuardrail)

    # selection audit
    selection: ActionSelection

    # graph context (for reproducibility)
    service_health: str = "healthy"
    anomaly_kind: str = "NORMAL"    # ISOLATED / UPSTREAM / CASCADING / NORMAL
    upstream: list[str] = Field(default_factory=list)
    downstream: list[str] = Field(default_factory=list)
    blast_members: list[str] = Field(default_factory=list)

    # policy (filled by Validation Layer — leave null until then)
    policy_outcome: PolicyOutcome | None = None
    policy_reason: str | None = None

    # bookkeeping
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ── helpers ───────────────────────────────────────────────────
    def to_log_row(self) -> dict[str, Any]:
        """Flatten into the exact columns of decision_log."""
        return {
            "id": self.decision_id,
            "anomaly_id": self.anomaly_id,
            "service_id": self.service_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "action": self.action.value,
            "action_params": self.action_params,
            "detection_conf": self.detection_conf,
            "rule_conf": self.rule_conf,
            "final_conf": self.final_conf,
            "base_risk": self.base_risk.value,
            "blast_factor": self.blast_factor,
            "centrality": self.centrality,
            "effective_severity": self.severity.effective_severity,
            "policy_outcome": self.policy_outcome.value if self.policy_outcome else None,
            "policy_reason": self.policy_reason,
            "context": {
                "severity": self.severity.model_dump(mode="json"),
                "selection": self.selection.model_dump(mode="json"),
                "service_health": self.service_health,
                "anomaly_kind": self.anomaly_kind,
                "upstream": self.upstream,
                "downstream": self.downstream,
                "blast_members": self.blast_members,
            },
            "created_at": self.created_at.isoformat(),
        }