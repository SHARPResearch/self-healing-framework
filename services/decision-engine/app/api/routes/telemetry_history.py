"""
History endpoints. Given a service_id, return recent snapshot points
(from anomalies) so the UI can chart trends.
"""
from fastapi import APIRouter
from app.persistence.timescale import timescale_store

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/{service_id}")
async def service_history(service_id: str, limit: int = 100):
    return await timescale_store.get_service_history(service_id, limit)


@router.get("/infra/{anomaly_id}")
async def infra_for_anomaly(anomaly_id: str):
    return await timescale_store.get_infra_snapshots(anomaly_id)


@router.get("/app/{anomaly_id}")
async def app_for_anomaly(anomaly_id: str):
    return await timescale_store.get_app_snapshots(anomaly_id)