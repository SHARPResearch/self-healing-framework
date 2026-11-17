# services/decision-engine/app/decision/validation/risk_classifier.py
"""
Risk classifier — combines three signals into a final RiskLevel.

    final_risk = max(
        base_risk_from_rule,              # LOW / MEDIUM / HIGH — from the rule
        blast.recommended_risk,           # LOW / MEDIUM / HIGH — from BlastRadiusAnalysis
        repeat_failure_bump,              # bumps to HIGH when repeat-failure ≥ 2
    )

The "max" semantics mean the *worst* signal wins — a low-risk rule that
happens to fire on a hub still ends up HIGH, which is what we want.

The repeated-failure bump is fed from `action_history` (see Postgres
methods in Phase 2). The orchestrator queries it once and passes the
count in, so this module stays pure / synchronous.
"""
from __future__ import annotations

from app.decision.blast_analysis import BlastRadiusAnalysis
from app.rules.models import RiskLevel


_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
_LABEL = {0: RiskLevel.LOW, 1: RiskLevel.MEDIUM, 2: RiskLevel.HIGH}

REPEAT_FAILURE_THRESHOLD = 2       # design doc §3.5.3 — "≥ 2 failures → escalate"


def classify_risk(
    base_risk: RiskLevel,
    blast: BlastRadiusAnalysis,
    *,
    repeat_failure_count: int = 0,
) -> tuple[RiskLevel, str]:
    """
    Return (final_risk, rationale).

    rationale is a comma-separated list of every signal that raised the
    level — useful in logs and in decision_log.context.
    """
    base_n = _ORDER[base_risk]
    blast_n = _ORDER[blast.recommended_risk]

    bumped = base_n
    reasons: list[str] = []

    if blast_n > bumped:
        reasons.append(
            f"blast radius recommends {blast.recommended_risk.value} "
            f"(size={blast.size}, factor={blast.factor:.2f})"
        )
        bumped = blast_n
    elif blast_n == base_n:
        reasons.append(f"base_risk and blast both {blast.recommended_risk.value}")

    if repeat_failure_count >= REPEAT_FAILURE_THRESHOLD:
        if bumped < _ORDER[RiskLevel.HIGH]:
            reasons.append(
                f"repeat-failure bump ({repeat_failure_count} prior failures)"
            )
        bumped = _ORDER[RiskLevel.HIGH]

    final = _LABEL[bumped]
    if not reasons:
        reasons.append(f"base_risk={base_risk.value}, blast={blast.recommended_risk.value}")

    return final, "; ".join(reasons)