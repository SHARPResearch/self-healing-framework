# # services/decision-engine/app/api/routes/executions.py
# """
# Execution log endpoints (Phase B).

#     GET /api/decisions/executions          list recent executions
#     GET /api/decisions/executions?service=X  filter by service
# """
# from __future__ import annotations

# from fastapi import APIRouter, Query

# router = APIRouter(prefix="/api/decisions/executions", tags=["decisions"])


# @router.get("")
# async def list_executions(
#     limit: int = Query(100, ge=1, le=500),
#     service_id: str | None = None,
# ):
#     from app.persistence.postgres import postgres_store
#     rows = await postgres_store.list_executions(limit=limit, service_id=service_id)
#     return {"count": len(rows), "executions": rows}


# services/decision-engine/app/api/routes/executions.py
"""
Execution log endpoints (Phase B).

    GET /api/executions                 list recent executions
    GET /api/executions?service=X       filter by service

Note: mounted at /api/executions (NOT /api/decisions/executions) to
avoid colliding with GET /api/decisions/{decision_id} in decisions.py.
FastAPI matches routes in registration order, so a nested path would
never win against the {decision_id} wildcard.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/executions", tags=["executions"])


@router.get("")
async def list_executions(
    limit: int = Query(100, ge=1, le=500),
    service_id: str | None = None,
):
    from app.persistence.postgres import postgres_store
    rows = await postgres_store.list_executions(limit=limit, service_id=service_id)
    return {"count": len(rows), "executions": rows}