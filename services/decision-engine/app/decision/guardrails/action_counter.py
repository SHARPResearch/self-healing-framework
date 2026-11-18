# services/decision-engine/app/decision/guardrails/action_counter.py
"""
Action counter — "has this service hit its per-hour action cap?"

The cap comes from the rule's guardrails:
    `recovery_action.guardrails["max_per_hour"]`  (default 3)

Counts are derived from `action_history` (Phase 2 DDL) — no new table.
We count any recorded action (SUCCESS or FAILED) in the last hour.
UNKNOWN / NEUTRAL outcomes are also counted; only the timestamp matters.

This is a sliding-window count. If the DB is unreachable, the check
fails-open (allow) and logs a warning — matching the store's behavior.
"""
from __future__ import annotations

import logging
from typing import Any

from app.decision.guardrails.verdict import GuardrailCheck

log = logging.getLogger(__name__)

DEFAULT_MAX_PER_HOUR = 3


def _resolve_cap(guardrails: dict[str, Any] | None) -> int:
    if not guardrails:
        return DEFAULT_MAX_PER_HOUR
    raw = guardrails.get("max_per_hour")
    if raw is None:
        return DEFAULT_MAX_PER_HOUR
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = DEFAULT_MAX_PER_HOUR
    return max(1, v)


async def check(service_id: str, guardrails: dict[str, Any] | None) -> GuardrailCheck:
    cap = _resolve_cap(guardrails)

    try:
        from app.persistence.postgres import postgres_store
        recent = await postgres_store.count_recent_actions(service_id, window_min=60)
    except Exception:
        log.exception("action_counter: Postgres lookup failed (fail-open)")
        return GuardrailCheck(
            name="action_counter",
            blocked=False,
            reason="counter check skipped (DB unavailable, fail-open)",
            detail={"cap": cap},
        )

    if recent >= cap:
        return GuardrailCheck(
            name="action_counter",
            blocked=True,
            reason=f"service '{service_id}' reached {recent}/{cap} actions in the last hour",
            detail={"count": recent, "cap": cap},
        )

    return GuardrailCheck(
        name="action_counter",
        blocked=False,
        reason=f"{recent}/{cap} actions in the last hour",
        detail={"count": recent, "cap": cap},
    )