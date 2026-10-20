"""
The important endpoint. Given an anomaly_id, return:
  - the anomaly row
  - all infra snapshots around it (T-30s .. T+30s)
  - all app snapshots around it
This is the "evidence bundle".
"""
from fastapi import APIRouter, HTTPException
from app.persistence.postgres import postgres_store
from app.persistence.timescale import timescale_store

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


@router.get("/{anomaly_id}/evidence")
async def anomaly_evidence(anomaly_id: str):
    anomaly = await postgres_store.get_anomaly(anomaly_id)
    if not anomaly:
        raise HTTPException(404, f"anomaly {anomaly_id} not found")

    infra = await timescale_store.get_infra_snapshots(anomaly_id)
    app = await timescale_store.get_app_snapshots(anomaly_id)

    return {
        "anomaly": anomaly,
        "infra_snapshots": infra,
        "app_snapshots": app,
        "counts": {
            "infra": len(infra),
            "app": len(app),
        },
    }


@router.get("/recent")
async def recent_anomalies(limit: int = 50):
    return await postgres_store.list_recent_anomalies(limit)

from app.ingestion.anomaly_sink import _capture_phase1, _capture_phase2

@router.post("/capture/{anomaly_id}")
async def force_capture(anomaly_id: str):
    """Manually trigger a two-phase snapshot for testing."""
    anomaly = await postgres_store.get_anomaly(anomaly_id)
    if not anomaly:
        raise HTTPException(404, f"anomaly {anomaly_id} not found")

    # Reset status so we can re-run
    async with postgres_store.pool.acquire() as conn:
        await conn.execute(
            "UPDATE anomaly_events SET snapshot_status='pending' WHERE id=$1",
            anomaly_id,
        )

    # Run both phases back to back (only works if ring buffer still has data)
    await _capture_phase1(anomaly_id, anomaly["service_id"], anomaly["detected_at"])
    await _capture_phase2(anomaly_id, anomaly["service_id"], anomaly["detected_at"])

    return {"ok": True, "anomaly_id": anomaly_id}

@router.get("/with-decisions")
async def anomalies_with_decisions(limit: int = 200):
    """
    List anomalies enriched with their decision (if any).
    One row per anomaly. If a decision exists, decision_* fields are populated.
    """
    rows = await postgres_store.list_anomalies_with_decisions(limit=limit)
    # Normalize datetimes to ISO strings for JSON
    for r in rows:
        for k, v in list(r.items()):
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
    return {"count": len(rows), "items": rows}