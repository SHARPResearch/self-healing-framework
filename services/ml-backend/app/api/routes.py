"""
routes.py — REST API under /api (contract documented in services/ml-backend/README.md).
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api import views
from app.bus import envelope
from app.logs import public as public_log
from app.runtime import runtime

router = APIRouter(prefix="/api")


def _service(service_id: str):
    rt = runtime.fleet.services.get(service_id)
    if rt is None:
        raise HTTPException(404, f"unknown service {service_id}")
    return rt


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "store": runtime.store.kind,
            "db": runtime.store.kind == "timescaledb" and getattr(runtime.store, "pool", None) is not None,
            "redis": runtime.bus.redis_ok, "services": len(runtime.fleet.services),
            "tick": runtime.tick, "eventsPerSec": runtime.events_per_sec, "paused": runtime.paused,
            "uptimeS": round(time.time() - runtime.started_at)}


# -- anomaly detection --------------------------------------------------------------------------
@router.get("/services")
async def services() -> list[dict]:
    return [views.service_health(runtime.fleet, rt) for rt in runtime.fleet.services.values()]


@router.get("/services/{service_id}/scores")
async def scores(service_id: str, limit: int = Query(300, le=600)) -> list[dict]:
    rt = _service(service_id)
    return [{"step": s, "score": v, "alarm": a, "threshold": 0.5} for s, v, a in list(rt.scores)[-limit:]]


@router.get("/dashboard/summary")
async def dashboard_summary() -> dict:
    rts = list(runtime.fleet.services.values())
    trend = await runtime.store.score_trend(30)
    decisions_all = [d for rt in rts for d in rt.manager.decisions]
    return {
        "activeAlarms": sum(1 for rt in rts if rt.last_alarm),
        "servicesInQuarantine": sum(1 for rt in rts if views.drift_detected(rt)),
        "openQueries": sum(len(rt.manager.open_queries) for rt in rts),
        "modelUpdates": sum(1 for d in decisions_all if d.get("action") in ("promote", "rollback")),
        "decisions": len(decisions_all),
        "anomalyTrend": [{"label": p["bucket"][11:16], "score": round(p["score"], 4)} for p in trend],
        "counts": await runtime.store.counts(),
    }


# -- dynamic model updating ---------------------------------------------------------------------
@router.get("/models")
async def models() -> list[dict]:
    return [views.model_run(runtime.fleet, rt) for rt in runtime.fleet.services.values()]


@router.get("/models/{service_id}")
async def model_detail(service_id: str) -> dict:
    return views.model_detail(runtime.fleet, _service(service_id))


class VersionBody(BaseModel):
    version: Optional[int] = None
    operator: str = "operator"


@router.post("/models/{service_id}/promote")
async def promote(service_id: str, body: VersionBody) -> dict:
    rt = _service(service_id)
    version = body.version or max(v.version for v in rt.manager.registry.versions)
    return await _manual(rt, version, "promote", body.operator)


@router.post("/models/{service_id}/rollback")
async def rollback(service_id: str, body: VersionBody) -> dict:
    rt = _service(service_id)
    version = body.version or _before_last_promotion(rt)
    if version is None:
        raise HTTPException(409, "no earlier production version to roll back to")
    return await _manual(rt, version, "rollback", body.operator)


def _before_last_promotion(rt) -> Optional[int]:
    """Undo the most recent promotion. Scheduled checkpoints also register versions, so the plain
    previous production version is usually a checkpoint of the very model being rolled back."""
    current = rt.manager.registry.production_version
    for t in reversed(rt.manager.registry.transitions):
        if t.transition == "promote" and t.from_version is not None and t.from_version != current:
            return t.from_version
    prev = rt.manager.registry.previous_production()
    return prev.version if prev else None


async def _manual(rt, version: int, transition: str, operator: str) -> dict:
    try:
        decision = rt.manager.manual_set_version(version, transition, operator=operator)
    except KeyError:
        raise HTTPException(404, f"no version {version}")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    await runtime.drain(rt)
    return {"decision": views._decision(decision), "model": views.model_run(runtime.fleet, rt)}


@router.post("/models/{service_id}/validity-check")
async def validity_check(service_id: str) -> dict:
    rt = _service(service_id)
    opened = rt.manager.request_validity_check()
    await runtime.drain(rt)
    if not opened:
        raise HTTPException(409, f"model is {rt.manager.phase}; a check is already running")
    return {"phase": rt.manager.phase}


@router.get("/lifecycle/decisions")
async def lifecycle_decisions(service_id: Optional[str] = None, limit: int = Query(100, le=500)) -> list[dict]:
    rts = [_service(service_id)] if service_id else list(runtime.fleet.services.values())
    rows = [d for rt in rts for d in views.decisions(rt, limit)]
    return sorted(rows, key=lambda d: d["step"] or 0, reverse=True)[:limit]


# -- operator in the loop -----------------------------------------------------------------------
@router.get("/queries")
async def list_queries(status: Optional[str] = None) -> list[dict]:
    return views.queries(runtime.fleet, status)


class AnswerBody(BaseModel):
    answer: Literal["new_normal", "incident"]
    operator: str = "operator"


@router.post("/queries/{query_id}/answer")
async def answer_query(query_id: str, body: AnswerBody) -> dict:
    for rt in runtime.fleet.services.values():
        if query_id in rt.manager.queries:
            try:
                decision = rt.manager.answer_query(query_id, body.answer, operator=body.operator)
            except KeyError as exc:
                raise HTTPException(409, str(exc))
            except RuntimeError as exc:
                raise HTTPException(409, str(exc))
            await runtime.drain(rt)
            return {"decision": views._decision(decision), "model": views.model_run(runtime.fleet, rt)}
    raise HTTPException(404, f"unknown query {query_id}")


# -- logs ---------------------------------------------------------------------------------------
def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@router.get("/logs")
async def logs(q: str = "", since: Optional[datetime] = None, until: Optional[datetime] = None,
               before: Optional[datetime] = None, limit: int = Query(500, ge=1, le=2000)) -> dict:
    """
    Log lines oldest first: the newest `limit` that match. `q` is the page's filter box (free text
    plus service:, level: and source: terms). Pass the oldest returned time as `before` to page
    further back; `hasMore` says whether anything older matched.
    """
    await runtime.flush_logs()
    rows = await runtime.store.query_logs(q, _utc(since), _utc(until), _utc(before), limit + 1)
    has_more = len(rows) > limit
    return {"lines": [public_log(r) for r in rows[-limit:]], "hasMore": has_more}


@router.get("/logs/histogram")
async def logs_histogram(q: str = "", since: Optional[datetime] = None,
                         until: Optional[datetime] = None) -> dict:
    """Matching lines per time bucket and level, for the bar strip above the log table."""
    await runtime.flush_logs()
    end = _utc(until) or datetime.now(timezone.utc)
    start = _utc(since) or end - timedelta(hours=1)
    return await runtime.store.log_histogram(q, start, end)


@router.get("/logs/services")
async def logs_services() -> list[dict]:
    """Every service that has logged, with its line count (the page's service filter)."""
    await runtime.flush_logs()
    return await runtime.store.log_services()


# -- demo controls ------------------------------------------------------------------------------
@router.get("/demo/state")
async def demo_state() -> dict:
    return {"eventsPerSec": runtime.events_per_sec, "paused": runtime.paused, "tick": runtime.tick,
            "services": [{"serviceId": rt.service_id, "displayName": rt.display_name,
                          "smdEntity": rt.entity, "step": rt.manager.step,
                          "injections": [i.kind for i in rt.injections]}
                         for rt in runtime.fleet.services.values()]}


@router.post("/demo/{service_id}/{kind}")
async def demo_inject(service_id: str, kind: Literal["deploy", "silent_change", "incident"]) -> dict:
    _service(service_id)
    return await runtime.inject(service_id, kind)


class SpeedBody(BaseModel):
    eventsPerSec: Optional[float] = None
    paused: Optional[bool] = None


@router.post("/demo/speed")
async def demo_speed(body: SpeedBody) -> dict:
    if body.eventsPerSec is not None:
        runtime.events_per_sec = max(0.5, min(200.0, body.eventsPerSec))
    if body.paused is not None:
        runtime.paused = body.paused
    await runtime.bus.publish(envelope("demo_speed", None, {"eventsPerSec": runtime.events_per_sec,
                                                            "paused": runtime.paused}))
    return {"eventsPerSec": runtime.events_per_sec, "paused": runtime.paused}


@router.post("/demo/reset")
async def demo_reset() -> dict:
    await runtime.reset()
    return {"status": "reset"}
