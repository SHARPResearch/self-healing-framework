"""
Rule models — the rule language.

A rule is:
    applies_to   → which services it can fire on
    when         → condition AST (all / any / leaf comparisons)
    then         → action + params + base_confidence + base_risk
    guardrails   → cooldown, rate limits, idempotency key

The `when` block is a recursive tree:
    RuleCondition = AllCondition | AnyCondition | LeafCondition

LeafCondition supports operators:
    ">", ">=", "<", "<=", "==", "!=", "in", "not_in", "contains"

Metric paths are dotted strings resolved against the Context:
    "anomaly.score", "service.layer", "infra.cpu.usage_pct",
    "app.latency_ms.p99", "graph.centrality", "blast_radius.factor"
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Union

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────
class ActionType(str, Enum):
    """Every recovery action the engine knows about."""
    RESTART_POD              = "RESTART_POD"
    SCALE_UP                 = "SCALE_UP"
    SCALE_DOWN               = "SCALE_DOWN"
    ROLLBACK                 = "ROLLBACK"
    OPEN_CIRCUIT             = "OPEN_CIRCUIT"
    CLOSE_CIRCUIT            = "CLOSE_CIRCUIT"
    FLUSH_CACHE              = "FLUSH_CACHE"
    INCREASE_DB_POOL         = "INCREASE_DB_POOL"
    SCALE_CONSUMERS          = "SCALE_CONSUMERS"
    DRAIN_NODE               = "DRAIN_NODE"
    NOOP                     = "NOOP"


class RiskLevel(str, Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"


class ConditionOp(str, Enum):
    GT       = ">"
    GTE      = ">="
    LT       = "<"
    LTE      = "<="
    EQ       = "=="
    NEQ      = "!="
    IN       = "in"
    NOT_IN   = "not_in"
    CONTAINS = "contains"


class RuleStatus(str, Enum):
    """Lifecycle of a rule. Only ACTIVE rules are evaluated by the engine."""
    DRAFT    = "DRAFT"
    ACTIVE   = "ACTIVE"
    ARCHIVED = "ARCHIVED"


# ─────────────────────────────────────────────────────────────────────
# Condition AST
# ─────────────────────────────────────────────────────────────────────
class LeafCondition(BaseModel):
    """One comparison: metric OP value."""
    metric: str = Field(..., description="Dotted path into Context")
    op: ConditionOp
    value: Any = Field(..., description="Scalar, list, or string")

    model_config = {"extra": "forbid"}


class AllCondition(BaseModel):
    """AND — every sub-condition must be true."""
    all: list["ConditionNode"]

    model_config = {"extra": "forbid"}


class AnyCondition(BaseModel):
    """OR — at least one sub-condition must be true."""
    any: list["ConditionNode"]

    model_config = {"extra": "forbid"}


ConditionNode = Union[LeafCondition, AllCondition, AnyCondition]


# Discriminated union for parsing JSON from DB
RuleCondition = Union[AllCondition, AnyCondition, LeafCondition]


# ─────────────────────────────────────────────────────────────────────
# Rule parts
# ─────────────────────────────────────────────────────────────────────
class RuleAction(BaseModel):
    """What to do when the rule fires."""
    action: ActionType
    params: dict[str, Any] = Field(default_factory=dict)
    base_confidence: float = Field(0.80, ge=0.0, le=1.0)
    base_risk: RiskLevel = RiskLevel.MEDIUM


class RuleGuardrail(BaseModel):
    """Safety rails applied at execution time."""
    cooldown_seconds: int = Field(300, ge=0)
    max_per_hour: int = Field(3, ge=1)
    idempotency_key: str | None = Field(
        None,
        description="Template string; supports {{ service.id }}, {{ anomaly.id }}",
    )


class RuleAppliesTo(BaseModel):
    """Where the rule is allowed to fire."""
    layers: list[str] = Field(default_factory=list)        # e.g. ["domain","bff"]
    services: list[str] = Field(default_factory=list)      # explicit IDs or ["*"]
    exclude_services: list[str] = Field(default_factory=list)

    def matches(self, layer: str, service_id: str) -> bool:
        if self.layers and layer not in self.layers:
            return False
        if service_id in self.exclude_services:
            return False
        if self.services and "*" not in self.services and service_id not in self.services:
            return False
        return True


# ─────────────────────────────────────────────────────────────────────
# The Rule itself
# ─────────────────────────────────────────────────────────────────────
class Rule(BaseModel):
    """A complete rule as stored in Postgres."""
    id: str
    version: int = 1
    priority: int = Field(100, description="Higher = evaluated first")
    description: str = ""
    enabled: bool = True

    applies_to: RuleAppliesTo = Field(default_factory=RuleAppliesTo)
    when: RuleCondition
    then: RuleAction
    guardrails: RuleGuardrail = Field(default_factory=RuleGuardrail)

    tags: list[str] = Field(default_factory=list)

    # ── ownership / lifecycle (Component 2 — Hybrid Rule Management) ──
    is_default: bool = Field(
        False, description="SHARP-owned rule: cannot be deleted, action is frozen"
    )
    is_template: bool = Field(
        False, description="Read-only starting point offered by SHARP"
    )
    created_by: str = "system"
    owner_org_id: str | None = None
    status: RuleStatus = RuleStatus.ACTIVE
    parent_rule_id: str | None = Field(
        None, description="Set when this rule was cloned from another rule"
    )

    # Populated on read only — never written back by upsert()
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("id")
    @classmethod
    def _id_slug(cls, v: str) -> str:
        if not v or not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("rule id must be slug-like (a-z, 0-9, -, _)")
        return v


# ─────────────────────────────────────────────────────────────────────
# Level 2 — partial customization payload (thresholds / priority only)
# ─────────────────────────────────────────────────────────────────────
class RuleCustomizationPayload(BaseModel):
    """
    Safe subset of a rule. This is what PATCH /api/rules/{id} accepts.

    `then` and `id` are deliberately present so the API can *detect* an
    attempt to change the shape of a rule and reject it with a 400 rather
    than silently dropping it (or a 422 from an unknown field). They are
    only ever applied to non-default rules.
    """
    priority: int | None = None
    when: RuleCondition | None = None
    then: RuleAction | None = None
    applies_to: RuleAppliesTo | None = None
    guardrails: RuleGuardrail | None = None
    enabled: bool | None = None
    description: str | None = None
    status: RuleStatus | None = None
    tags: list[str] | None = None
    id: str | None = None

    model_config = {"extra": "forbid"}


# ─────────────────────────────────────────────────────────────────────
# Level 3 — full custom rule payload
# ─────────────────────────────────────────────────────────────────────
class CreateCustomRulePayload(BaseModel):
    """Everything the Advanced Rule Builder can produce."""
    id: str
    description: str
    when: RuleCondition
    then: RuleAction
    guardrails: RuleGuardrail = Field(default_factory=RuleGuardrail)
    applies_to: RuleAppliesTo = Field(default_factory=RuleAppliesTo)
    priority: int = 100
    tags: list[str] = Field(default_factory=list)
    status: RuleStatus = RuleStatus.ACTIVE
    parent_rule_id: str | None = None

    @field_validator("id")
    @classmethod
    def _id_slug(cls, v: str) -> str:
        if not v or not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("rule id must be slug-like (a-z, 0-9, -, _)")
        return v


# ─────────────────────────────────────────────────────────────────────
# Candidate — what a matched rule produces
# ─────────────────────────────────────────────────────────────────────
class RuleCandidate(BaseModel):
    """A rule that matched, with the blended confidence already computed."""
    rule_id: str
    rule_version: int
    priority: int

    action: ActionType
    params: dict[str, Any]

    base_confidence: float
    detection_confidence: float
    final_confidence: float            # 0.6*detection + 0.4*base

    base_risk: RiskLevel
    blast_factor: float = 1.0
    centrality: float = 1.0

    guardrails: RuleGuardrail
    matched_at_metrics: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def blend(detection: float, base: float) -> float:
        """Component 2 spec: 0.6*detection + 0.4*rule."""
        return round(0.6 * detection + 0.4 * base, 4)


# Resolve forward refs
AllCondition.model_rebuild()
AnyCondition.model_rebuild()