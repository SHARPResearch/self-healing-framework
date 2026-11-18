# services/decision-engine/app/api/routes/escalations.py
"""
Escalation endpoints (design doc §3.5.3).

    GET  /api/decisions/escalations              list escalations
    GET  /api/decisions/escalations/{id}         get one
    POST /api/decisions/escalations/{id}/ack     operator acknowledgement
    POST /api/decisions/escalations/{id}/fire    force-fire next attempt (debug)

Note: postgres_store is imported *inside* each endpoint so tests can
monkeypatch `app.persistence.postgres.postgres_store` cleanly. Top-level
imports bypass the monkeypatch because FastAPI holds a reference to the
function object, not the module.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.decision.escalation import ack as esc_ack
from app.decision.escalation import list_pending
from app.decision.escalation import queue as esc_queue

router = APIRouter(prefix="/api/decisions/escalations", tags=["decisions"])


@router.get("")
async def list_escalations(
    status: str | None = Query(None, description="PENDING | AWAITING_HUMAN | RESOLVED | MANUAL_REQUIRED"),
    limit: int = Query(100, ge=1, le=500),
):
    from app.persistence.postgres import postgres_store
    statuses = [status] if status else None
    rows = await postgres_store.list_escalations(statuses=statuses, limit=limit)
    return {"count": len(rows), "escalations": rows}


@router.get("/pending")
async def pending():
    escs = await list_pending()
    return {"count": len(escs), "escalations": [e.to_dict() for e in escs]}


@router.get("/{escalation_id}")
async def get_escalation(escalation_id: str):
    from app.persistence.postgres import postgres_store
    row = await postgres_store.get_escalation(escalation_id)
    if not row:
        raise HTTPException(404, f"escalation {escalation_id} not found")
    return row


@router.post("/{escalation_id}/ack")
async def acknowledge(
    escalation_id: str,
    decision: str = Query("APPROVED", pattern="^(APPROVED|REJECTED)$"),
    actor: str = Query("unknown"),
    note: str = Query(""),
):
    esc = await esc_ack(escalation_id, actor=actor, decision=decision, note=note)
    if esc is None:
        raise HTTPException(404, f"escalation {escalation_id} not found")
    return {"ok": True, "escalation": esc.to_dict()}


@router.post("/{escalation_id}/fire")
async def fire_now(escalation_id: str):
    """Debug: force the worker to fire the next attempt immediately."""
    from app.persistence.postgres import postgres_store
    row = await postgres_store.get_escalation(escalation_id)
    if not row:
        raise HTTPException(404, f"escalation {escalation_id} not found")

    row["next_attempt_at"] = datetime.now(timezone.utc)
    await postgres_store.save_escalation(row)

    from app.decision.escalation.worker import fire_due_attempts
    fired = await fire_due_attempts()

    row2 = await postgres_store.get_escalation(escalation_id)
    return {"ok": True, "fired": fired, "escalation": row2}