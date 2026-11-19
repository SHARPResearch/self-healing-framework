# services/decision-engine/app/decision/escalation/__init__.py
"""
Public surface of the Escalation subsystem.

    from app.decision.escalation import escalate, ack, list_pending

`ack()` is not a plain re-export: approving an escalation is what turns a
HUMAN_LOOP decision into an executed action, so this wrapper records the
verdict (queue.ack) and then runs the executor for an APPROVED verdict
(approval.execute_approved). The result is stored inside the escalation's
`response` field so the audit trail answers "what did the approval do?".
"""
from __future__ import annotations

import logging

from app.decision.escalation.approval import execute_approved
from app.decision.escalation.queue import (
    Escalation,
    EscalationStatus,
    ack as _ack,
    enqueue as _enqueue,
    list_pending,
    set_response,
)

log = logging.getLogger(__name__)


async def escalate(
    decision_id: str,
    anomaly_id: str,
    service_id: str,
) -> Escalation:
    """
    Convenience wrapper — create an escalation from a decision.
    Called by job.py when validation.outcome == HUMAN_LOOP.
    """
    return await _enqueue(
        decision_id=decision_id,
        anomaly_id=anomaly_id,
        service_id=service_id,
    )


async def ack(
    escalation_id: str,
    actor: str = "unknown",
    decision: str = "APPROVED",
    note: str = "",
) -> Escalation | None:
    """
    Record the operator's verdict, then act on it when it was APPROVED.

    Idempotent: a second ack returns the stored row and does not execute again
    (the execution summary is already in `response`). A REJECTED verdict never
    executes. An execution failure is captured in the response rather than
    raised, so acknowledging always succeeds even if the executor is down.
    """
    esc = await _ack(escalation_id, actor=actor, decision=decision, note=note)
    if esc is None:
        return None

    response = dict(esc.response or {})

    # Only a positive verdict that was actually recorded triggers execution.
    if response.get("decision") != "APPROVED":
        return esc
    if response.get("execution"):
        return esc

    try:
        response["execution"] = await execute_approved(esc.decision_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("ack: executing approved decision %s failed", esc.decision_id)
        response["execution"] = {
            "status": "FAILED",
            "message": f"execution attempt failed: {exc}",
        }

    await set_response(esc, response)
    return esc


__all__ = [
    "escalate",
    "ack",
    "list_pending",
    "Escalation",
    "EscalationStatus",
]
