# services/decision-engine/app/decision/blast_analysis.py
"""
Blast Radius Analysis — the *decision-facing* view of blast radius.

`core/blast_radius.py` answers "how big is the reverse-reachable set?" and
"what factor maps into [1.0, 1.5]?". That's the *graph* answer.

The Validation Layer needs a different question answered:

    "If I execute THIS action on THIS service, what is the collateral?"

That's what this module produces: a `BlastRadiusAnalysis` object that is
consumed by the Risk Classifier (Phase 2). It is intentionally action-
aware — restarting a leaf pod and restarting a hub are very different.

Design note
-----------
We do NOT duplicate graph traversal. We delegate to
`BlastRadiusAnalyzer` (reverse_reachable / size / factor / weighted) and
add the decision-facing annotations on top:

    * member list            (already in AnomalyContext.blast_members)
    * max member criticality (worst downstream neighbor)
    * is_hub / is_leaf       (crude but useful shortcut)
    * action multiplier      (some actions are intrinsically riskier)
    * recommended risk level (LOW / MEDIUM / HIGH)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.blast_radius import BlastRadiusAnalyzer
from app.core.graph_store import GraphStore
from app.rules.models import ActionType, RiskLevel

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Action intrinsic risk — how dangerous is this action *in isolation*,
# ignoring graph context? Multiplied into the graph-derived risk.
# ─────────────────────────────────────────────────────────────────────
_ACTION_INTRINSIC_RISK: dict[ActionType, float] = {
    ActionType.RESTART_POD:      0.20,   # low — one pod, fast
    ActionType.SCALE_UP:         0.15,   # low — adds capacity
    ActionType.SCALE_CONSUMERS:  0.15,   # low — adds consumers
    ActionType.FLUSH_CACHE:      0.30,   # medium — brief cold-cache window
    ActionType.INCREASE_DB_POOL: 0.35,   # medium — DB pressure
    ActionType.OPEN_CIRCUIT:     0.40,   # medium — traffic shift
    ActionType.CLOSE_CIRCUIT:    0.35,   # medium — traffic reopens
    ActionType.SCALE_DOWN:       0.55,   # high — removes capacity
    ActionType.ROLLBACK:         0.60,   # high — version flip
    ActionType.DRAIN_NODE:       0.80,   # very high — evacuates a node
    ActionType.NOOP:             0.00,
}


@dataclass
class BlastRadiusAnalysis:
    """
    Decision-facing blast radius summary for one (service, action) pair.

    All numeric fields are computed for the given service. `action` only
    affects the intrinsic-risk adjustment and the recommended level.
    """
    service_id: str
    action: ActionType

    # raw graph facts
    size: int                                  # number of reverse-reachable services
    factor: float                              # [1.0, 1.5] — same scale as ctx.blast_factor
    weighted: float                            # Σ(criticality × strength)
    members: list[str] = field(default_factory=list)
    max_member_criticality: float = 1.0        # worst downstream neighbor

    # annotations
    is_hub: bool = False                       # size >= 5 (widely depended-on)
    is_leaf: bool = False                      # size == 0 (nobody depends on it)
    intrinsic_risk: float = 0.0                # [0.0, 1.0] — from action type alone

    # decision-facing recommendation
    recommended_risk: RiskLevel = RiskLevel.LOW
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "action": self.action.value,
            "size": self.size,
            "factor": round(self.factor, 4),
            "weighted": round(self.weighted, 4),
            "members": list(self.members),
            "max_member_criticality": round(self.max_member_criticality, 4),
            "is_hub": self.is_hub,
            "is_leaf": self.is_leaf,
            "intrinsic_risk": round(self.intrinsic_risk, 4),
            "recommended_risk": self.recommended_risk.value,
            "rationale": self.rationale,
        }


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────
class BlastRadiusAnalyzerDecision:
    """
    Thin wrapper that reuses the graph analyzer + adds decision-facing
    annotations. Stateless — safe to instantiate per call or as a
    module-level singleton.
    """

    HUB_THRESHOLD = 5           # reverse-reachable >= 5 → hub
    HIGH_FACTOR = 1.35          # factor ≥ 1.35 → high-collateral
    MEDIUM_FACTOR = 1.15

    def __init__(self, store: GraphStore | None = None):
        self.store = store or GraphStore()
        self._graph_analyzer = BlastRadiusAnalyzer(self.store)

    def analyze(
        self,
        service_id: str,
        action: ActionType,
        criticality: dict[str, float] | None = None,
    ) -> BlastRadiusAnalysis:
        """
        Build the full decision-facing blast-radius view for one action.

        `criticality` is optional — if omitted, all members default to 1.0.
        Callers typically pass `{sid: ctx.service.get("criticality", 1.0)}`
        or the full map.
        """
        crit = criticality or {}

        members = sorted(self._graph_analyzer.reverse_reachable(service_id))
        size = len(members)
        factor = self._graph_analyzer.factor(service_id)
        weighted = self._graph_analyzer.weighted(service_id, crit) if crit else float(size)

        max_member_crit = max((crit.get(m, 1.0) for m in members), default=1.0)

        intrinsic = _ACTION_INTRINSIC_RISK.get(action, 0.5)
        is_hub = size >= self.HUB_THRESHOLD
        is_leaf = size == 0

        risk, rationale = self._recommend(
            action=action,
            size=size,
            factor=factor,
            intrinsic=intrinsic,
            is_hub=is_hub,
            is_leaf=is_leaf,
            max_member_crit=max_member_crit,
        )

        return BlastRadiusAnalysis(
            service_id=service_id,
            action=action,
            size=size,
            factor=factor,
            weighted=weighted,
            members=members,
            max_member_criticality=max_member_crit,
            is_hub=is_hub,
            is_leaf=is_leaf,
            intrinsic_risk=intrinsic,
            recommended_risk=risk,
            rationale=rationale,
        )

    # ── recommendation ────────────────────────────────────────────
    def _recommend(
        self,
        *,
        action: ActionType,
        size: int,
        factor: float,
        intrinsic: float,
        is_hub: bool,
        is_leaf: bool,
        max_member_crit: float,
    ) -> tuple[RiskLevel, str]:
        # ── 1. Fast exits ────────────────────────────────────────
        # Leaf + low-intrinsic action is unambiguously safe.
        if is_leaf and intrinsic <= 0.30:
            return (
                RiskLevel.LOW,
                f"leaf service (0 dependents) + low-risk action ({action.value})",
            )

        # ── 2. Intrinsically dangerous action → HIGH regardless ──
        if intrinsic >= 0.55:
            return (
                RiskLevel.HIGH,
                f"action '{action.value}' is intrinsically high-risk "
                f"(intrinsic={intrinsic:.2f})",
            )

        # ── 3. Hub service → HIGH (per design doc §5.4) ──────────
        # A "hub" means many services depend on it. Restarting /
        # scaling / circuit-breaking a hub propagates. This fires
        # before the factor test because the log-scaled `factor` only
        # reaches ~1.5 with 100+ dependents, which would make hubs of
        # realistic size (5–20) miss the HIGH band entirely.
        if is_hub:
            return (
                RiskLevel.HIGH,
                f"hub service ({size} dependents) — action '{action.value}' "
                f"would propagate (factor={factor:.2f})",
            )

        # ── 4. Medium band ───────────────────────────────────────
        # Not a hub, but factor or member criticality is meaningful,
        # or the action is non-trivial.
        if factor >= self.MEDIUM_FACTOR or max_member_crit >= 0.85 or intrinsic >= 0.35:
            reasons = []
            if factor >= self.MEDIUM_FACTOR:
                reasons.append(f"factor={factor:.2f}")
            if max_member_crit >= 0.85:
                reasons.append(f"max_member_criticality={max_member_crit:.2f}")
            if intrinsic >= 0.35:
                reasons.append(f"intrinsic={intrinsic:.2f}")
            return RiskLevel.MEDIUM, ", ".join(reasons)

        return (
            RiskLevel.LOW,
            f"small blast radius ({size} dependents, factor={factor:.2f}) "
            f"+ low-risk action '{action.value}'",
        )


# Module-level singleton (matches rule_engine pattern)
blast_analysis = BlastRadiusAnalyzerDecision()