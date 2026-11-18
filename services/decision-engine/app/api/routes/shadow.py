# services/decision-engine/app/api/routes/shadow.py
"""
Shadow Mode endpoints.

    GET  /api/decisions/shadow                     list shadow records
    GET  /api/decisions/shadow/metrics             §8.2 aggregate metrics
    GET  /api/decisions/shadow/{shadow_id}         get one
    POST /api/decisions/shadow/{shadow_id}/resolve manual close (demo)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.decision.shadow_observer import resolve_manually

router = APIRouter(prefix="/api/decisions/shadow", tags=["decisions"])


@router.get("")
async def list_shadows(
    limit: int = Query(100, ge=1, le=500),
    verdict: str | None = Query(None, description="Filter by verdict"),
    service_id: str | None = Query(None),
):
    from app.persistence.postgres import postgres_store
    rows = await postgres_store.list_shadows(
        limit=limit, verdict=verdict, service_id=service_id
    )
    return {"count": len(rows), "shadows": rows}


@router.get("/metrics")
async def metrics():
    from app.persistence.postgres import postgres_store
    return await postgres_store.shadow_metrics()


@router.get("/{shadow_id}")
async def get_shadow(shadow_id: str):
    from app.persistence.postgres import postgres_store
    row = await postgres_store.get_shadow(shadow_id)
    if not row:
        raise HTTPException(404, f"shadow {shadow_id} not found")
    return row


@router.post("/{shadow_id}/resolve")
async def resolve(
    shadow_id: str,
    resolved_naturally: bool = Query(
        True, description="True = anomaly self-resolved; False = would have needed help"
    ),
    resolution_time_sec: int = Query(60, ge=0, le=86400),
):
    """Manual close — useful for the demo UI and for cleanup after incidents."""
    row = await resolve_manually(
        shadow_id,
        resolved_naturally=resolved_naturally,
        resolution_time_sec=resolution_time_sec,
    )
    if not row:
        raise HTTPException(404, f"shadow {shadow_id} not found")
    return {"ok": True, "shadow": row}