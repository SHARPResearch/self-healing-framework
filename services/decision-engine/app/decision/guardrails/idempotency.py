# services/decision-engine/app/decision/guardrails/idempotency.py
"""
Idempotency guardrail — "have we already executed this exact action?"

Prevents the same intent from being executed twice. The key is derived
from the rule's `guardrails.idempotency_key` template (or a default
composition) and rendered against the current (service, anomaly, action).

Template tokens (per rule language spec):
    {{ service.id }}     → recovery_action.service_id
    {{ anomaly.id }}     → decision_id's anomaly_id (passed in)
    {{ action }}         → recovery_action.action.value

Default when no template exists:
    idem:{service_id}:{action}:{anomaly_id}

Persistence:
    * Postgres `idempotency_keys` (Phase 3 DDL) — source of truth
    * Redis/in-memory cache                    — hot path

TTL: rules can set `guardrails.idempotency_ttl_sec` (default 86400 = 24h).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.decision.action_selector import RecoveryAction
from app.decision.guardrails.store import get_store
from app.decision.guardrails.verdict import GuardrailCheck

log = logging.getLogger(__name__)

DEFAULT_TTL_SEC = 86400     # 24 hours


def _resolve_ttl(guardrails: dict[str, Any] | None) -> int:
    if not guardrails:
        return DEFAULT_TTL_SEC
    raw = guardrails.get("idempotency_ttl_sec")
    if raw is None:
        return DEFAULT_TTL_SEC
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = DEFAULT_TTL_SEC
    return max(60, v)


def _render_template(template: str | None, ra: RecoveryAction, anomaly_id: str) -> str:
    if not template:
        return f"idem:{ra.service_id}:{ra.action.value}:{anomaly_id or 'unknown'}"
    return (
        template
        .replace("{{ service.id }}", ra.service_id)
        .replace("{{service.id}}", ra.service_id)
        .replace("{{ anomaly.id }}", anomaly_id or "unknown")
        .replace("{{anomaly.id}}", anomaly_id or "unknown")
        .replace("{{ action }}", ra.action.value)
        .replace("{{action}}", ra.action.value)
    )


async def check(
    recovery_action: RecoveryAction,
    anomaly_id: str,
) -> GuardrailCheck:
    key = _render_template(
        recovery_action.guardrails.get("idempotency_key") if recovery_action.guardrails else None,
        recovery_action,
        anomaly_id,
    )

    # ── 1. Cache ──────────────────────────────────────────────────
    store = get_store()
    try:
        if await store.exists(key):
            return GuardrailCheck(
                name="idempotency",
                blocked=True,
                reason=f"action already executed for key '{key}'",
                detail={"key": key, "cache_hit": True},
            )
    except Exception:
        log.exception("idempotency: cache lookup failed (fail-open)")

    # ── 2. Postgres ───────────────────────────────────────────────
    try:
        from app.persistence.postgres import postgres_store
        existing = await postgres_store.get_idempotency_key(key)
    except Exception:
        log.exception("idempotency: Postgres lookup failed (fail-open)")
        existing = None

    if existing:
        ttl = _resolve_ttl(recovery_action.guardrails)
        # Backfill cache so next check is fast
        try:
            await store.set(key, existing["decision_id"], ttl)
        except Exception:
            log.debug("idempotency: cache repopulation skipped")

        return GuardrailCheck(
            name="idempotency",
            blocked=True,
            reason=f"action already executed (key='{key}', decision={existing['decision_id']})",
            detail={"key": key, "cache_hit": False, "existing_decision": existing["decision_id"]},
        )

    return GuardrailCheck(
        name="idempotency",
        blocked=False,
        reason=f"new intent (key='{key}')",
        detail={"key": key, "cache_hit": False},
    )


async def mark(
    recovery_action: RecoveryAction,
    anomaly_id: str,
    decision_id: str,
) -> None:
    """
    Record this decision as having executed its idempotent intent.
    Called by guardrails.check() on overall PASS.
    """
    key = _render_template(
        recovery_action.guardrails.get("idempotency_key") if recovery_action.guardrails else None,
        recovery_action,
        anomaly_id,
    )
    ttl = _resolve_ttl(recovery_action.guardrails)
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)

    try:
        from app.persistence.postgres import postgres_store
        await postgres_store.save_idempotency_key(key, decision_id, expires)
    except Exception:
        log.exception("idempotency: Postgres write failed")

    try:
        store = get_store()
        await store.set(key, decision_id, ttl)
    except Exception:
        log.exception("idempotency: cache write failed")