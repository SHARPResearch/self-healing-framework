
# services/decision-engine/app/decision/guardrails/guardrails.py
"""
Guardrails orchestrator.

    check(recovery_action, anomaly_id) -> GuardrailVerdict

Runs every guardrail in order. Short-circuits on the first blocker — we
don't need to know whether the idempotency key also collided if a
cooldown is already blocking, and short-circuiting saves DB round-trips.

Order matters for cost and clarity:
    1. cooldown          — cheapest when cache hits, most decisive
    2. action_counter    — one COUNT query
    3. idempotency       — one lookup, then one write on PASS

On overall PASS, `mark()` is called for cooldown + idempotency (side
effect: they start tracking this decision). `action_counter` has no
side effect — it counts from action_history, which is written by the
execution path (Phase 4 job wiring).

Persistence failures never block the decision. Every sub-check fails
open (allow). This is deliberate: a working guardrail is nice; a
permanently blocked pipeline is not.
"""
from __future__ import annotations

import logging

from app.decision.action_selector import RecoveryAction
from app.decision.guardrails import action_counter, cooldown, idempotency
from app.decision.guardrails.verdict import (
    GuardrailCheck,
    GuardrailVerdict,
    allow,
    block,
)

log = logging.getLogger(__name__)


async def check(
    recovery_action: RecoveryAction,
    anomaly_id: str,
) -> GuardrailVerdict:
    """
    Run every guardrail. Return the aggregate verdict.
    Caller is responsible for calling `mark()` if the verdict is allowed.
    """
    checks: list[GuardrailCheck] = []

    # ── 1. Cooldown ──────────────────────────────────────────────
    try:
        c = await cooldown.check(recovery_action.service_id, recovery_action.guardrails)
    except Exception:
        log.exception("guardrails: cooldown check crashed (fail-open)")
        c = GuardrailCheck(name="cooldown", blocked=False, reason="check crashed (fail-open)")
    checks.append(c)
    if c.blocked:
        return block(checks, c)

    # ── 2. Action counter ────────────────────────────────────────
    try:
        c = await action_counter.check(recovery_action.service_id, recovery_action.guardrails)
    except Exception:
        log.exception("guardrails: action_counter check crashed (fail-open)")
        c = GuardrailCheck(name="action_counter", blocked=False, reason="check crashed (fail-open)")
    checks.append(c)
    if c.blocked:
        return block(checks, c)

    # ── 3. Idempotency ───────────────────────────────────────────
    try:
        c = await idempotency.check(recovery_action, anomaly_id)
    except Exception:
        log.exception("guardrails: idempotency check crashed (fail-open)")
        c = GuardrailCheck(name="idempotency", blocked=False, reason="check crashed (fail-open)")
    checks.append(c)
    if c.blocked:
        return block(checks, c)

    return allow(checks)


async def mark(
    recovery_action: RecoveryAction,
    anomaly_id: str,
    decision_id: str,
) -> None:
    """
    Record side effects for guardrails that track state (cooldown,
    idempotency). Call ONLY after `check()` returned `allowed=True`
    and the decision has actually been persisted/executed.

    Never throws — every write is best-effort.
    """
    try:
        await cooldown.mark(recovery_action.service_id, decision_id, recovery_action.guardrails)
    except Exception:
        log.exception("guardrails.mark: cooldown.mark failed")

    try:
        await idempotency.mark(recovery_action, anomaly_id, decision_id)
    except Exception:
        log.exception("guardrails.mark: idempotency.mark failed")