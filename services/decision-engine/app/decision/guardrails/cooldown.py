# services/decision-engine/app/decision/guardrails/cooldown.py
"""
Cooldown guardrail — "has this service had an action too recently?"

Two-layer persistence (per your E confirmation):
    * Postgres `cooldowns` table — the source of truth, survives restart
    * Redis (or in-memory) cache  — hot path, avoids a DB query per decision

Semantics:
    * The cooldown window is derived from the *rule's guardrail*:
      `recovery_action.guardrails["cooldown_seconds"]`. If missing,
      a service default (settings.DEFAULT_COOLDOWN_SEC, coded 300) is used.
    * "Action too recently" means: an action on this service executed
      within `cooldown_seconds`.
    * We do NOT track per-action cooldown — cooldown is per-service,
      because two different actions on the same service still constitute
      a burst.

On PASS, the caller (guardrails.check) is expected to *mark* the service
as acted-upon, starting a new cooldown. The marking happens in `mark()`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.decision.guardrails.store import get_store
from app.decision.guardrails.verdict import GuardrailCheck

log = logging.getLogger(__name__)

DEFAULT_COOLDOWN_SEC = 300


def _key(service_id: str) -> str:
    return f"cooldown:{service_id}"


def _resolve_window_sec(guardrails: dict[str, Any] | None) -> int:
    if not guardrails:
        return DEFAULT_COOLDOWN_SEC
    raw = guardrails.get("cooldown_seconds")
    if raw is None:
        return DEFAULT_COOLDOWN_SEC
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = DEFAULT_COOLDOWN_SEC
    return max(0, v)


async def check(service_id: str, guardrails: dict[str, Any] | None) -> GuardrailCheck:
    """
    Return PASS unless this service has an active cooldown.
    """
    window = _resolve_window_sec(guardrails)
    if window <= 0:
        return GuardrailCheck(
            name="cooldown",
            blocked=False,
            reason="cooldown disabled (window=0)",
            detail={"window_sec": 0},
        )

    # ── 1. Cache hit? ─────────────────────────────────────────────
    store = get_store()
    try:
        hit = await store.get(_key(service_id))
    except Exception:
        log.exception("cooldown: cache lookup failed (fail-open)")
        hit = None

    if hit:
        return GuardrailCheck(
            name="cooldown",
            blocked=True,
            reason=f"service '{service_id}' acted on within the last {window}s",
            detail={"window_sec": window, "cache_hit": True, "last_action_at": hit},
        )

    # ── 2. Cache miss — check Postgres ────────────────────────────
    try:
        from app.persistence.postgres import postgres_store
        active = await postgres_store.get_active_cooldown(service_id)
    except Exception:
        log.exception("cooldown: Postgres lookup failed (fail-open)")
        active = None

    if active:
        # Repopulate the cache from Postgres so the next check is fast.
        try:
            expires: datetime = active["expires_at"]
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            remaining = (expires - datetime.now(timezone.utc)).total_seconds()
            if remaining > 0:
                await store.set(_key(service_id), active["started_at"].isoformat(), int(remaining))
        except Exception:
            log.debug("cooldown: cache repopulation skipped")

        return GuardrailCheck(
            name="cooldown",
            blocked=True,
            reason=f"service '{service_id}' acted on within the last {window}s",
            detail={
                "window_sec": window,
                "cache_hit": False,
                "last_action_at": str(active["started_at"]),
                "expires_at": str(active["expires_at"]),
            },
        )

    return GuardrailCheck(
        name="cooldown",
        blocked=False,
        reason=f"no active cooldown (window={window}s)",
        detail={"window_sec": window, "cache_hit": False},
    )


async def mark(service_id: str, decision_id: str, guardrails: dict[str, Any] | None) -> None:
    """
    Start a fresh cooldown for this service. Called by guardrails.check()
    when the overall verdict is PASS — this is the "action happened"
    bookkeeping step. Idempotent per decision_id.
    """
    window = _resolve_window_sec(guardrails)
    if window <= 0:
        return

    expires = datetime.now(timezone.utc) + timedelta(seconds=window)

    # Postgres — source of truth
    try:
        from app.persistence.postgres import postgres_store
        await postgres_store.upsert_cooldown(service_id, decision_id, expires)
    except Exception:
        log.exception("cooldown: Postgres write failed")

    # Cache — best-effort
    try:
        store = get_store()
        await store.set(_key(service_id), datetime.now(timezone.utc).isoformat(), window)
    except Exception:
        log.exception("cooldown: cache write failed")