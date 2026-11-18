# services/decision-engine/app/decision/escalation/__init__.py
"""
Public surface of the Escalation subsystem.

    from app.decision.escalation import escalate, ack, list_pending
"""
from app.decision.escalation.queue import (
    Escalation,
    EscalationStatus,
    ack,
    enqueue as _enqueue,
    list_pending,
)


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


__all__ = [
    "escalate",
    "ack",
    "list_pending",
    "Escalation",
    "EscalationStatus",
]