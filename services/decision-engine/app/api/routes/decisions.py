"""
Decision endpoints.

    POST /api/decisions/evaluate/{anomaly_id}   run engine + save
    GET  /api/decisions/recent                   list recent decisions
    GET  /api/decisions/{decision_id}            get one decision
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.routes.mock_data import _anomaly, _app, _infra, SERVICES
from app.decision.log import (
    build_decision,
    persist_decision,
    row_to_decision,
)
from app.persistence.postgres import postgres_store
from app.rules.classifier import classify
from app.rules.context import ContextBuilder
from app.rules.engine import rule_engine

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/decisions", tags=["decisions"])


# ─────────────────────────────────────────────────────────────────────
# POST — Evaluate a real anomaly, save to DB, return the decision
# ─────────────────────────────────────────────────────────────────────
@router.post("/evaluate/{anomaly_id}")
async def evaluate_anomaly(anomaly_id: str, save: bool = True):
    """
    Manually evaluate a mock anomaly through the Rule Engine + Severity +
    Action Selector, and (optionally) save the decision to Postgres.
    """
    # 1. Fetch the anomaly from Postgres (must have been captured already)
    anomaly = await postgres_store.get_anomaly(anomaly_id)
    if not anomaly:
        # Fallback: try to build from mock_data directly
        sid = _sid_from_anomaly_id(anomaly_id)
        if not sid or sid not in SERVICES:
            raise HTTPException(
                404,
                f"anomaly {anomaly_id} not found in DB and cannot be built from mock",
            )
        anomaly = _anomaly(sid)  # type: ignore[assignment]
        if not anomaly:
            raise HTTPException(
                404,
                f"service {sid} is currently healthy; no anomaly to evaluate",
            )

    sid = anomaly["service_id"]

    # 2. Fetch all recent anomalies so the classifier can see neighbors
    try:
        recent = await postgres_store.list_recent_anomalies(limit=50)
    except Exception:
        recent = []

    # 3. Build context (with recent anomalies so neighbor counting works)
    builder = ContextBuilder()
    builder.set_services_catalog(SERVICES)
    ctx = builder.build(
        anomaly,
        infra=_infra(sid),
        app=_app(sid),
        recent_anomalies=recent,
    )
    classify(ctx)

    # 3. Evaluate rules
    candidates = rule_engine.evaluate(ctx)

    # 4. Build decision
    decision = build_decision(ctx, candidates)
    if decision is None:
        return {
            "ok": True,
            "anomaly_id": anomaly_id,
            "service_id": sid,
            "decision": None,
            "reason": "no rule matched this anomaly",
            "context": ctx.to_dict(),
        }

    # 5. Save
    saved = False
    if save:
        saved = await persist_decision(decision)

    return {
        "ok": True,
        "anomaly_id": anomaly_id,
        "saved": saved,
        "decision": row_to_decision(decision.to_log_row()),
        "context": ctx.to_dict(),
    }


# ─────────────────────────────────────────────────────────────────────
# GET — Fetch one decision
# ─────────────────────────────────────────────────────────────────────
@router.get("/recent")
async def recent_decisions(
    limit: int = Query(50, ge=1, le=500),
    service_id: str | None = None,
    policy_outcome: str | None = None,
):
    rows = await postgres_store.list_decisions(
        limit=limit,
        service_id=service_id,
        policy_outcome=policy_outcome,
    )
    return {
        "count": len(rows),
        "decisions": [row_to_decision(r) for r in rows],
    }


@router.get("/{decision_id}")
async def get_decision(decision_id: str):
    row = await postgres_store.get_decision(decision_id)
    if not row:
        raise HTTPException(404, f"decision {decision_id} not found")
    return row_to_decision(row)

@router.get("/incidents")
async def list_incidents():
    """Debug — show all service incident states."""
    return await postgres_store.get_all_incident_states()

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _sid_from_anomaly_id(anomaly_id: str) -> str | None:
    """
    'ANM-auth_outage-auth-service' → 'auth-service'
    Works with our deterministic mock IDs: ANM-{scenario}-{service_id}
    """
    parts = anomaly_id.split("-")
    if len(parts) < 3 or parts[0] != "ANM":
        return None
    # scenario may contain hyphens (auth_outage → auth_outage; but
    # kafka_lag → kafka_lag; database_degraded → database_degraded)
    # service IDs contain hyphens too. So assume last 2 parts = service,
    # and everything between = scenario. But 2-part services like
    # "web-bff" break this. Safer: match against SERVICES keys.
    for sid in SERVICES.keys():
        if anomaly_id.endswith(sid):
            return sid
    return None