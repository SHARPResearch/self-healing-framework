# services/decision-engine/app/decision/shadow_observer.py
"""
Shadow Mode outcome observer.

Runs on APScheduler every SHADOW_OBSERVE_INTERVAL_SEC. For each shadow
record where VERDICT IS NULL and created_at < NOW() - SHADOW_MIN_AGE_SEC:

    1. Look at the anomaly's resolution state (snapshot_status, health).
    2. Check whether a matching escalation was acked APPROVED/REJECTED.
    3. Classify:
         * resolved without intervention   → resolved_naturally=True
         * resolved via approved escalation → resolved_naturally=False
         * rejected escalation             → UNKNOWN
         * still active after MAX_WAIT     → ANOMALY_STILL_ACTIVE (terminal, no verdict)
         * still active but within MAX_WAIT → skip (retry next cycle)
    4. Call observe_shadow_outcome() to fill VERDICT + LEARNING.
    5. Persist via postgres_store.update_shadow_outcome().

The observer is idempotent: the WHERE VERDICT IS NULL filter plus
ON CONFLICT DO UPDATE means a crash-and-retry never double-writes.

Design doc §4.4 defines the counterfactual record. This module fills in
ACTUAL_OUTCOME, VERDICT, LEARNING — completing the record.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.decision.validation.shadow import observe_shadow_outcome
from app.persistence.postgres import postgres_store

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Outcome classification
# ─────────────────────────────────────────────────────────────────────
async def _classify_outcome(
    shadow_row: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Decide the counterfactual outcome for one shadow row.

    Returns:
        None                    → skip (not yet eligible, retry next cycle)
        {"terminal": True, ...} → mark ANOMALY_STILL_ACTIVE, no verdict
        {"resolved_naturally": bool, "resolution_time_sec": int} → verdict
    """
    service_id = shadow_row["service_id"]
    anomaly_id = shadow_row["anomaly_id"]
    created_at = shadow_row.get("created_at")
    if created_at is None:
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_sec = int((now - created_at).total_seconds())

    # ── 1. Escalation check ─────────────────────────────────────
    esc = await postgres_store.get_escalation_by_decision(shadow_row["decision_id"])

    if esc:
        status = esc.get("status")
        response = esc.get("response") or {}
        if isinstance(response, str):
            import json
            try:
                response = json.loads(response)
            except Exception:
                response = {}

        if status == "RESOLVED" and response.get("decision") == "APPROVED":
            # Resolved via human action. In shadow mode we didn't execute
            # the candidate, so this is the "would have helped" signal.
            ack_at = response.get("at")
            resolution_sec = _seconds_between(created_at, ack_at) or age_sec
            return {
                "resolved_naturally": False,
                "resolution_time_sec": resolution_sec,
                "resolution_path": "ESCALATION_APPROVED",
            }

        if status == "RESOLVED" and response.get("decision") == "REJECTED":
            # Operator declined — nothing was done. UNKNOWN outcome.
            return {
                "resolved_naturally": False,
                "resolution_time_sec": age_sec,
                "resolution_path": "ESCALATION_REJECTED",
                "force_verdict": "UNKNOWN",
            }

        if status == "MANUAL_REQUIRED":
            # Nobody acted. Treat as unresolved within budget.
            return {
                "resolved_naturally": False,
                "resolution_time_sec": age_sec,
                "resolution_path": "MANUAL_REQUIRED",
                "force_verdict": "ACTION_WOULD_HAVE_HELPED",
            }

        # Still awaiting human — leave the row alone; retry next cycle
        if status in ("PENDING", "AWAITING_HUMAN"):
            return None

    # ── 2. Anomaly health check ─────────────────────────────────
    anomaly = await postgres_store.get_anomaly(anomaly_id)
    if not anomaly:
        return None  # anomaly got deleted — odd, but leave the shadow open

    # Did the anomaly's snapshot complete (post-window captured)?
    snapshot_status = anomaly.get("snapshot_status")
    captured_at = anomaly.get("captured_at")
    if captured_at and captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)

    # Is the service healthy NOW?
    incident = await postgres_store.get_incident_state(service_id)
    healthy_now = (
        incident is not None
        and (incident.get("current_health") or "").lower() == "healthy"
        and incident.get("incident_start") is None
    )

    if healthy_now and snapshot_status == "captured":
        # The anomaly resolved on its own (no escalation, no action taken).
        resolution_sec = _seconds_between(created_at, captured_at) or age_sec
        return {
            "resolved_naturally": True,
            "resolution_time_sec": resolution_sec,
            "resolution_path": "NATURAL",
        }

    # ── 3. Timeout: still active after MAX_WAIT ─────────────────
    max_wait_sec = int(getattr(settings, "SHADOW_MAX_WAIT_MIN", 60)) * 60
    if age_sec > max_wait_sec:
        return {
            "terminal": True,
            "resolution_path": "STILL_ACTIVE",
            "age_sec": age_sec,
        }

    # Still within budget → retry next cycle
    return None


def _seconds_between(start, end) -> int | None:
    """Return whole seconds between two datetimes (tz-aware or strings)."""
    def _to_dt(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return None

    s = _to_dt(start)
    e = _to_dt(end)
    if s is None or e is None:
        return None
    return max(0, int((e - s).total_seconds()))


# ─────────────────────────────────────────────────────────────────────
# Public: single-cycle worker
# ─────────────────────────────────────────────────────────────────────
async def observe_once() -> int:
    """
    Run one observation cycle. Returns the number of shadow records
    whose outcome was finalized this cycle.
    """
    min_age = int(getattr(settings, "SHADOW_MIN_AGE_SEC", 300))
    due = await postgres_store.list_open_shadows(min_age_sec=min_age, limit=200)
    if not due:
        return 0

    finalized = 0
    for row in due:
        try:
            outcome = await _classify_outcome(row)
            if outcome is None:
                continue

            # Terminal, no-verdict case (still active past MAX_WAIT)
            if outcome.get("terminal"):
                await postgres_store.mark_shadow_abandoned(
                    shadow_id=row["id"],
                    reason="ANOMALY_STILL_ACTIVE",
                    observed_at=datetime.now(timezone.utc),
                )
                finalized += 1
                continue

            # Build the verdict + learning via the existing helper
            updated = observe_shadow_outcome(
                _row_to_payload(row),
                resolved_naturally=bool(outcome["resolved_naturally"]),
                resolution_time_sec=int(outcome["resolution_time_sec"]),
            )

            # Manual override for REJECTED / MANUAL_REQUIRED cases
            if outcome.get("force_verdict"):
                updated["VERDICT"] = outcome["force_verdict"]
                updated["LEARNING"] = (
                    f"force verdict from resolution_path="
                    f"{outcome.get('resolution_path')}"
                )

            await postgres_store.update_shadow_outcome(
                shadow_id=row["id"],
                actual_outcome=updated["ACTUAL_OUTCOME"],
                verdict=updated["VERDICT"],
                learning=updated["LEARNING"],
                observed_at=datetime.now(timezone.utc),
                resolved_at=_resolution_timestamp(
                    row, outcome.get("resolution_time_sec", 0)
                ),
            )
            finalized += 1
            log.info(
                "Shadow %s resolved: %s (%s, %ds)",
                row["id"],
                updated["VERDICT"],
                outcome.get("resolution_path"),
                int(outcome.get("resolution_time_sec", 0)),
            )
        except Exception:
            log.exception("shadow_observer: failed to finalize %s", row.get("id"))

    return finalized


def _resolution_timestamp(row: dict, resolution_sec: int) -> datetime:
    created = row.get("created_at")
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            created = None
    if created is None:
        return datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return created + timedelta(seconds=resolution_sec)


def _row_to_payload(row: dict) -> dict[str, Any]:
    """
    Convert a DB row into the SHADOW-payload dict that
    observe_shadow_outcome() expects.
    """
    import json

    def _load(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        return v

    return {
        "SHADOW_ID": row["id"],
        "DECISION_ID": row["decision_id"],
        "ANOMALY_ID": row["anomaly_id"],
        "SERVICE": row["service_id"],
        "CANDIDATE_ACTION": row["candidate_action"],
        "CONFIDENCE": float(row["confidence"]),
        "RISK": row["risk"],
        "SIMULATED_OUTCOME": _load(row.get("simulated_outcome")) or {},
    }


# ─────────────────────────────────────────────────────────────────────
# Manual close (for demo / human override)
# ─────────────────────────────────────────────────────────────────────
async def resolve_manually(
    shadow_id: str,
    *,
    resolved_naturally: bool,
    resolution_time_sec: int,
) -> dict[str, Any] | None:
    """
    Force a verdict for a shadow record. Used by:
      * POST /api/decisions/shadow/{id}/resolve
      * Demo: "resolve this shadow now so you can see the verdict"
    """
    row = await postgres_store.get_shadow(shadow_id)
    if not row:
        return None
    if row.get("verdict"):
        return row  # already terminal

    updated = observe_shadow_outcome(
        _row_to_payload(row),
        resolved_naturally=resolved_naturally,
        resolution_time_sec=resolution_time_sec,
    )
    await postgres_store.update_shadow_outcome(
        shadow_id=shadow_id,
        actual_outcome=updated["ACTUAL_OUTCOME"],
        verdict=updated["VERDICT"],
        learning=updated["LEARNING"],
        observed_at=datetime.now(timezone.utc),
        resolved_at=_resolution_timestamp(row, resolution_time_sec),
    )
    return await postgres_store.get_shadow(shadow_id)


# ─────────────────────────────────────────────────────────────────────
# Scheduler
# ─────────────────────────────────────────────────────────────────────
def start_shadow_observer(scheduler: AsyncIOScheduler) -> None:
    interval = int(getattr(settings, "SHADOW_OBSERVE_INTERVAL_SEC", 60))
    scheduler.add_job(
        observe_once,
        "interval",
        seconds=interval,
        id="shadow_observer",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("Shadow observer scheduled (every %ss)", interval)