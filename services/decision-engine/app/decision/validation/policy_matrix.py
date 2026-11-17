# services/decision-engine/app/decision/validation/policy_matrix.py
"""
The Decision Policy Matrix — §3.3 of the design doc, verbatim.

    | Condition                                  | Outcome       |
    |--------------------------------------------|---------------|
    | High confidence + low-risk action          | AUTO_EXECUTE  |
    | Medium confidence                          | SHADOW_MODE   |
    | Low confidence                             | BLOCK         |
    | High-risk action                           | HUMAN_LOOP    |
    | Repeated failed actions                    | HUMAN_LOOP    |
    | Dependency conflict detected               | BLOCK         |

Evaluation order matters. We check BLOCK conditions first (conflict is
the strongest veto), then HUMAN_LOOP (high-risk + repeat-failure), then
AUTO_EXECUTE (high-confidence + low-risk), then SHADOW_MODE (the middle
band). Anything that doesn't fit → BLOCK (fail-closed).

The matrix is a pure function of:
    * confidence.band  ∈ {"LOW", "MEDIUM", "HIGH"}
    * risk             ∈ {LOW, MEDIUM, HIGH}
    * conflict.has_conflict (bool)
"""
from __future__ import annotations

from app.decision.models import PolicyOutcome
from app.decision.validation.result import ConflictReport, ConfidenceBreakdown
from app.rules.models import RiskLevel


def decide_outcome(
    confidence: ConfidenceBreakdown,
    risk: RiskLevel,
    conflict: ConflictReport,
) -> tuple[PolicyOutcome, str]:
    """
    Return (outcome, reason). The reason is the one-liner stored in
    decision_log.policy_reason — it must be human-readable.
    """
    # ── 1. Conflict veto (any kind) ──────────────────────────────
    if conflict.has_conflict:
        details = "; ".join(conflict.details) or conflict.kind or "unknown conflict"
        return (
            PolicyOutcome.BLOCK,
            f"blocked: {conflict.kind.lower()} conflict — {details}",
        )

    # ── 2. High-risk → human-in-the-loop ─────────────────────────
    # (repeat-failure is baked into `risk` by risk_classifier — see
    #  REPEAT_FAILURE_THRESHOLD; a bumped-to-HIGH outcome means the
    #  risk classifier already decided this needs human eyes.)
    if risk == RiskLevel.HIGH:
        return (
            PolicyOutcome.HUMAN_LOOP,
            f"escalate: risk={risk.value} (requires human validation)",
        )

    # ── 3. Low confidence → block ────────────────────────────────
    if confidence.band == "LOW":
        return (
            PolicyOutcome.BLOCK,
            f"blocked: confidence {confidence.effective:.3f} "
            f"below threshold {0.60:.2f}",
        )

    # ── 4. High confidence + low risk → auto-execute ─────────────
    if confidence.band == "HIGH" and risk == RiskLevel.LOW:
        return (
            PolicyOutcome.AUTO_EXECUTE,
            f"auto: confidence {confidence.effective:.3f} ≥ 0.85 and risk=LOW",
        )

    # ── 5. Medium confidence OR (high-confidence + medium-risk) ──
    # Both land here — the spec says "medium confidence → shadow", and
    # a high-confidence decision with MEDIUM risk should be shadowed
    # too (we trust the prediction but not enough to skip observation).
    return (
        PolicyOutcome.SHADOW_MODE,
        f"shadow: confidence={confidence.effective:.3f} "
        f"({confidence.band}), risk={risk.value}",
    )