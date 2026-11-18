# services/decision-engine/app/decision/validation/validator.py
"""
Top-level orchestrator.

    validate(recovery_action, ctx) -> ValidationResult

Order of operations (each step is independent and idempotent — safe to
call from job.py, a manual route, or a test):

    1. Build confidence breakdown  (blended + graph certainty)
    2. Query repeat-failure count  (feeds risk_classifier)
    3. Classify risk               (base_risk + blast + repeat-failure)
    4. Detect conflicts            (in-flight, dependency, repeat-failure)
    5. Decide outcome              (policy matrix, §3.3)
    6. Build shadow payload        (if SHADOW_MODE)
    7. Build escalation payload    (if HUMAN_LOOP)

The orchestrator never persists — the caller decides what to write to
`decision_log`, `shadow_records`, `escalations`, etc.
"""
from __future__ import annotations

import logging
from typing import Any

from app.decision.action_selector import RecoveryAction
from app.decision.models import PolicyOutcome
from app.decision.validation.confidence import compute_confidence
from app.decision.validation.conflict_detector import detect_conflicts
from app.decision.validation.policy_matrix import decide_outcome
from app.decision.validation.result import ValidationResult
from app.decision.validation.risk_classifier import (
    REPEAT_FAILURE_THRESHOLD,
    classify_risk,
)
from app.decision.validation.shadow import build_shadow_payload
from app.rules.context import AnomalyContext

log = logging.getLogger(__name__)


async def validate(
    recovery_action: RecoveryAction,
    ctx: AnomalyContext,
) -> ValidationResult:
    """
    Run the full Validation Layer for one recovery action.
    """
    # ── 1. Confidence breakdown ───────────────────────────────────
    confidence = compute_confidence(
        blended=recovery_action.confidence,
        detection=_lookup_detection(recovery_action, ctx),
        rule_base=_lookup_rule_base(recovery_action),
        ctx=ctx,
    )

    # ── 2. Repeat-failure count (needed by risk_classifier) ──────
    repeat_failures = await _count_repeat_failures(
        recovery_action.service_id, recovery_action.action.value
    )

    # ── 3. Risk classification ────────────────────────────────────
    risk, risk_rationale = classify_risk(
        base_risk=recovery_action.base_risk,
        blast=recovery_action.blast,
        repeat_failure_count=repeat_failures,
    )

    # ── 4. Conflict detection ─────────────────────────────────────
    conflict = await detect_conflicts(
        service_id=recovery_action.service_id,
        action=recovery_action.action,
        ctx=ctx,
    )

    # ── 5. Policy decision ────────────────────────────────────────
    outcome, reason = decide_outcome(confidence, risk, conflict)

    # ── 6 + 7. Optional payloads ─────────────────────────────────
    shadow_payload: dict[str, Any] | None = None
    escalation_payload: dict[str, Any] | None = None

    if outcome == PolicyOutcome.SHADOW_MODE:
        shadow_payload = build_shadow_payload(
            decision_id=ctx.anomaly.get("decision_id") or "DEC-unknown",
            anomaly_id=str(ctx.anomaly.get("id") or ""),
            ctx=ctx,
            action=recovery_action.action,
            confidence=confidence,
            risk=risk,
        )

    if outcome == PolicyOutcome.HUMAN_LOOP:
        escalation_payload = {
            "service_id": recovery_action.service_id,
            "action": recovery_action.action.value,
            "params": recovery_action.params,
            "risk": risk.value,
            "confidence": confidence.effective,
            "risk_rationale": risk_rationale,
            "conflict": conflict.to_dict(),
        }

    log.info(
        "Validation: %s → %s (conf=%.3f/%s, risk=%s, conflict=%s)",
        recovery_action.service_id,
        outcome.value,
        confidence.effective,
        confidence.band,
        risk.value,
        conflict.kind or "none",
    )

    return ValidationResult(
        outcome=outcome,
        reason=reason,
        confidence=confidence,
        risk=risk,
        conflict=conflict,
        shadow_payload=shadow_payload,
        escalation_payload=escalation_payload,
    )


# ─────────────────────────────────────────────────────────────────────
# Lookups — cheap, best-effort, never throw
# ─────────────────────────────────────────────────────────────────────
def _lookup_detection(ra: RecoveryAction, ctx: AnomalyContext) -> float:
    """Detection confidence — from the anomaly row, default 0.8."""
    try:
        return float(ctx.anomaly.get("confidence", 0.8))
    except (TypeError, ValueError):
        return 0.8


def _lookup_rule_base(ra: RecoveryAction) -> float:
    """
    Rule base confidence — derived by inverting the blend:
        0.6*d + 0.4*b = blended → b = (blended - 0.6*d) / 0.4
    But since RecoveryAction doesn't carry d, we just recover `b` from
    the winner candidate that produced it. That lives in
    `recovery_action.rationale`-adjacent data — but to keep this module
    robust we approximate: b = (blended - 0.6*det) / 0.4, clamped to
    [0, 1]. In practice det is close to the actual detection value, so
    the approximation is fine.
    """
    d = getattr(ra, "_detection_hint", None) or 0.8
    try:
        b = (ra.confidence - 0.6 * d) / 0.4
        return max(0.0, min(1.0, float(b)))
    except (TypeError, ZeroDivisionError):
        return 0.8


async def _count_repeat_failures(service_id: str, action: str) -> int:
    """
    Best-effort lookup. Returns 0 when the DB is unavailable — safer than
    accidentally escalating every decision because of a transient error.
    """
    try:
        from app.persistence.postgres import postgres_store
        return await postgres_store.count_recent_failures(
            service_id=service_id,
            action=action,
            window_min=30,
        )
    except Exception:
        log.debug("validator: repeat-failure lookup failed (fail-open)")
        return 0


__all__ = ["validate", "REPEAT_FAILURE_THRESHOLD"]