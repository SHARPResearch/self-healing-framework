# services/decision-engine/app/decision/validation/conflict_detector.py
"""
Conflict detection — three independent checks, any of which can veto a
decision before it leaves the Validation Layer.

    1. IN_FLIGHT    — the same service already has an action in progress
                      that hasn't expired (per in_flight_actions).

    2. DEPENDENCY   — an action is already in flight on an upstream or
                      downstream neighbor, which means our decision may be
                      reacting to *their* symptom rather than a local fault.

    3. REPEAT_FAILURE — the same (service, action) has already FAILED
                        REPEAT_FAILURE_THRESHOLD times in the recent
                        window (per action_history).

The detector is async because it queries Postgres. It never throws — any
DB error is logged and treated as "no conflict" (fail-open, safer than
silently blocking every decision when the DB is briefly unreachable).

`in_flight_actions` and `action_history` rows live in Postgres; there is
no Redis read here — that cache belongs to Phase 3 (guardrails).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.decision.validation.result import ConflictReport
from app.rules.context import AnomalyContext
from app.rules.models import ActionType

log = logging.getLogger(__name__)

REPEAT_FAILURE_THRESHOLD = 2       # design doc §3.5.3
REPEAT_FAILURE_WINDOW_MIN = 30     # lookback for repeat-failure counting


async def detect_conflicts(
    service_id: str,
    action: ActionType,
    ctx: AnomalyContext,
) -> ConflictReport:
    """
    Run all three checks. First conflict wins (short-circuits).
    """
    # ── 1. In-flight on the same service ──────────────────────────
    try:
        from app.persistence.postgres import postgres_store

        inflight_same = await postgres_store.list_in_flight(service_id)
        active_same = [
            r for r in inflight_same
            if r.get("expires_at") and r["expires_at"] > datetime.now(timezone.utc)
        ]
        if active_same:
            return ConflictReport(
                has_conflict=True,
                kind="IN_FLIGHT",
                details=[
                    f"action '{r['action']}' on '{r['service_id']}' already in flight "
                    f"(decision={r['decision_id']}, expires={r['expires_at'].isoformat()})"
                    for r in active_same
                ],
            )
    except Exception:
        log.exception("conflict_detector: in-flight lookup failed (fail-open)")

    # ── 2. Dependency conflict ────────────────────────────────────
    try:
        neighbor_ids = set(ctx.upstream) | set(ctx.downstream)
        if neighbor_ids:
            from app.persistence.postgres import postgres_store
            inflight_neighbors = await postgres_store.list_in_flight_multi(
                list(neighbor_ids)
            )
            active_neighbors = [
                r for r in inflight_neighbors
                if r.get("expires_at") and r["expires_at"] > datetime.now(timezone.utc)
            ]
            if active_neighbors:
                return ConflictReport(
                    has_conflict=True,
                    kind="DEPENDENCY",
                    details=[
                        f"action '{r['action']}' on neighbor '{r['service_id']}' "
                        f"in flight (decision={r['decision_id']})"
                        for r in active_neighbors
                    ],
                )
    except Exception:
        log.exception("conflict_detector: dependency lookup failed (fail-open)")

    # ── 3. Repeat-failure bump ────────────────────────────────────
    try:
        from app.persistence.postgres import postgres_store
        fail_count = await postgres_store.count_recent_failures(
            service_id=service_id,
            action=action.value,
            window_min=REPEAT_FAILURE_WINDOW_MIN,
        )
        if fail_count >= REPEAT_FAILURE_THRESHOLD:
            return ConflictReport(
                has_conflict=True,
                kind="REPEAT_FAILURE",
                details=[
                    f"'{action.value}' has failed {fail_count}× on '{service_id}' "
                    f"in the last {REPEAT_FAILURE_WINDOW_MIN} min",
                ],
            )
    except Exception:
        log.exception("conflict_detector: repeat-failure lookup failed (fail-open)")

    return ConflictReport(has_conflict=False)