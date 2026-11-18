# services/decision-engine/app/decision/escalation/queue.py
"""
Escalation queue — the persistence layer for human-in-the-loop.

State machine (design doc §3.6):

    PENDING          — created; first email not yet sent
        │
        ▼  (worker fires attempt 1)
    AWAITING_HUMAN   — email sent; waiting for ack
        │
        ├── operator acks         → RESOLVED   (terminal)
        ├── worker fires attempt 2 (reminder)
        ├── worker fires attempt 3 (final failure report)
        └── worker exhausts attempts → MANUAL_REQUIRED   (terminal)

Timings (design doc §3.5.3):
    T+0     → initial email
    T+5min  → reminder
    T+15min → final failure report → MANUAL_REQUIRED
"""
from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


class EscalationStatus(str, Enum):
    PENDING           = "PENDING"
    AWAITING_HUMAN    = "AWAITING_HUMAN"
    RESOLVED          = "RESOLVED"
    MANUAL_REQUIRED   = "MANUAL_REQUIRED"


# Time windows between attempts (design doc §3.5.3)
ATTEMPT_1_DELAY_SEC = 0        # send immediately
ATTEMPT_2_DELAY_SEC = 300      # 5 min after attempt 1
ATTEMPT_3_DELAY_SEC = 600      # 10 min after attempt 2 → T+15 min total


def make_escalation_id() -> str:
    now = datetime.now(timezone.utc)
    return f"ESC-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def _coerce_dt(v: Any) -> datetime | None:
    """Coerce datetime / ISO string / None → datetime | None."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v)
        except (ValueError, TypeError):
            return None
    return None


@dataclass
class Escalation:
    id: str
    decision_id: str
    anomaly_id: str
    service_id: str
    status: EscalationStatus = EscalationStatus.PENDING
    attempt: int = 0
    max_attempts: int = 3
    next_attempt_at: datetime | None = None
    notifications: list[dict] = field(default_factory=list)
    response: dict[str, Any] | None = None
    failure_report: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        # Defensive: coerce in case some caller passed a string
        return {
            "id": self.id,
            "decision_id": self.decision_id,
            "anomaly_id": self.anomaly_id,
            "service_id": self.service_id,
            "status": self.status.value,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "next_attempt_at": (
                _coerce_dt(self.next_attempt_at).isoformat()
                if self.next_attempt_at else None
            ),
            "notifications": self.notifications,
            "response": self.response,
            "failure_report": self.failure_report,
            "created_at": _coerce_dt(self.created_at).isoformat()
                if self.created_at else None,
            "updated_at": _coerce_dt(self.updated_at).isoformat()
                if self.updated_at else None,
        }


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────
async def enqueue(
    decision_id: str,
    anomaly_id: str,
    service_id: str,
    *,
    max_attempts: int = 3,
) -> Escalation:
    esc = Escalation(
        id=make_escalation_id(),
        decision_id=decision_id,
        anomaly_id=anomaly_id,
        service_id=service_id,
        max_attempts=max_attempts,
        next_attempt_at=datetime.now(timezone.utc),
    )
    await _persist(esc)
    log.info(
        "Escalation created: %s (decision=%s, service=%s)",
        esc.id, decision_id, service_id,
    )
    return esc


async def ack(
    escalation_id: str,
    actor: str = "unknown",
    decision: str = "APPROVED",
    note: str = "",
) -> Escalation | None:
    from app.persistence.postgres import postgres_store

    row = await postgres_store.get_escalation(escalation_id)
    if not row:
        log.warning("ack: escalation %s not found", escalation_id)
        return None

    esc = _row_to_escalation(row)
    if esc.status in (EscalationStatus.RESOLVED, EscalationStatus.MANUAL_REQUIRED):
        log.info("ack: escalation %s already terminal (%s)", escalation_id, esc.status.value)
        return esc

    esc.status = EscalationStatus.RESOLVED
    esc.response = {
        "decision": decision,
        "by": actor,
        "at": datetime.now(timezone.utc).isoformat(),
        "note": note,
    }
    esc.next_attempt_at = None
    esc.updated_at = datetime.now(timezone.utc)
    await _persist(esc)
    log.info("Escalation %s RESOLVED by %s (decision=%s)", escalation_id, actor, decision)
    return esc


async def list_pending() -> list[Escalation]:
    from app.persistence.postgres import postgres_store
    rows = await postgres_store.list_escalations(
        statuses=["PENDING", "AWAITING_HUMAN"],
        limit=200,
    )
    return [_row_to_escalation(r) for r in rows]


async def list_due(now: datetime | None = None) -> list[Escalation]:
    from app.persistence.postgres import postgres_store
    now = now or datetime.now(timezone.utc)
    rows = await postgres_store.list_escalations_due(now=now)
    return [_row_to_escalation(r) for r in rows]


async def record_attempt(
    escalation: Escalation,
    *,
    subject: str,
    body: str,
    sent: bool,
    error: str | None = None,
) -> Escalation:
    now = datetime.now(timezone.utc)
    escalation.attempt += 1
    escalation.notifications.append({
        "attempt": escalation.attempt,
        "sent_at": now.isoformat(),
        "subject": subject,
        "sent": sent,
        "error": error,
    })

    if sent and escalation.attempt < escalation.max_attempts:
        if escalation.attempt == 1:
            next_delay = ATTEMPT_2_DELAY_SEC
        else:
            next_delay = ATTEMPT_3_DELAY_SEC
        escalation.next_attempt_at = now + timedelta(seconds=next_delay)
        escalation.status = EscalationStatus.AWAITING_HUMAN
    elif escalation.attempt >= escalation.max_attempts:
        escalation.status = EscalationStatus.MANUAL_REQUIRED
        escalation.next_attempt_at = None
        escalation.failure_report = (
            f"All {escalation.max_attempts} attempts exhausted without operator "
            f"ack for decision {escalation.decision_id}. Manual intervention required."
        )
        log.warning(
            "Escalation %s MANUAL_REQUIRED — %d attempts exhausted",
            escalation.id, escalation.attempt,
        )
    else:
        escalation.next_attempt_at = now + timedelta(seconds=60)
        escalation.status = EscalationStatus.PENDING

    escalation.updated_at = now
    await _persist(escalation)
    return escalation


# ─────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────
async def _persist(esc: Escalation) -> None:
    from app.persistence.postgres import postgres_store
    await postgres_store.save_escalation(esc.to_dict())


def _row_to_escalation(row: dict) -> Escalation:
    notifications = row.get("notifications") or []
    if isinstance(notifications, str):
        try:
            notifications = json.loads(notifications)
        except Exception:
            notifications = []

    response = row.get("response")
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except Exception:
            response = None

    return Escalation(
        id=row["id"],
        decision_id=row["decision_id"],
        anomaly_id=row["anomaly_id"],
        service_id=row["service_id"],
        status=EscalationStatus(row["status"]),
        attempt=int(row.get("attempt", 0)),
        max_attempts=int(row.get("max_attempts", 3)),
        next_attempt_at=_coerce_dt(row.get("next_attempt_at")),
        notifications=notifications,
        response=response,
        failure_report=row.get("failure_report"),
        created_at=_coerce_dt(row.get("created_at")) or datetime.now(timezone.utc),
        updated_at=_coerce_dt(row.get("updated_at")) or datetime.now(timezone.utc),
    )