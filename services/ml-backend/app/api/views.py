"""
views.py — fleet state rendered in the shapes the React frontend already uses.

ServiceHealth  -> frontend/src/features/dashboard/types.ts
ModelRun       -> frontend/src/features/models/types.ts (extended with lifecycle fields)
"""

from datetime import datetime, timezone

from app.fleet import ServiceFleet, ServiceRuntime


def _iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else datetime.now(timezone.utc).isoformat()


def quarantine_trigger(rt: ServiceRuntime) -> str | None:
    mgr = rt.manager
    return getattr(mgr, "_q_trigger", None) if mgr.phase != "stable" else None


def drift_detected(rt: ServiceRuntime) -> bool:
    """Drift or a change is being investigated, or the operator was asked. A routine scheduled
    validity check (one day in every two) is not drift."""
    trigger = quarantine_trigger(rt)
    return (trigger is not None and trigger != "scheduled") or bool(rt.manager.open_queries)


def service_health(fleet: ServiceFleet, rt: ServiceRuntime) -> dict:
    mgr = rt.manager
    return {
        "serviceId": rt.service_id,
        "displayName": rt.display_name,
        "status": fleet.severity(rt),
        "anomalyScore": round(rt.last_display, 4),
        "scoreHistory": fleet.score_history(rt),
        "lastAction": rt.last_action,
        "lastActionAt": rt.last_action_at,
        "driftDetected": drift_detected(rt),
        # lifecycle extras
        "phase": mgr.phase,
        "quarantineTrigger": quarantine_trigger(rt),
        "alarm": rt.last_alarm,
        "modelVersion": mgr.registry.production_version,
        "openQueries": len(mgr.open_queries),
        "smdEntity": rt.entity + (f" (rows {rt.window_start}+)" if rt.window_start else ""),
        "source": rt.entity,
    }


def _stage(status: str) -> str:
    return {"production": "STREAMING", "archived": "ARCHIVED"}.get(status, "WARM_UP")


def model_versions(rt: ServiceRuntime) -> list[dict]:
    out = []
    for v in rt.manager.registry.versions:
        out.append({
            "version": v.version, "status": v.status, "stage": _stage(v.status),
            "threshold": round(v.threshold, 6), "createdStep": v.created_step,
            "kind": v.tags.get("kind"), "verdict": v.tags.get("verdict"), "reason": v.reason,
            "queryId": v.tags.get("query_id"), "operator": v.tags.get("operator"),
            "rebaselined": v.state.meta.get("shifts") or {},
        })
    return out


def transitions(rt: ServiceRuntime) -> list[dict]:
    return [{"seq": t.seq, "step": t.step, "transition": t.transition, "fromVersion": t.from_version,
             "toVersion": t.to_version, "reason": t.reason, "evidence": t.evidence,
             "time": _iso(t.wall_time)} for t in rt.manager.registry.transitions]


def decisions(rt: ServiceRuntime, limit: int = 50) -> list[dict]:
    return [_decision(d) for d in reversed(rt.manager.decisions[-limit:])]


def _decision(d: dict) -> dict:
    return {"serviceId": d.get("service_id"), "step": d.get("step"), "version": d.get("version"),
            "action": d.get("action"), "verdict": d.get("verdict"), "trigger": d.get("trigger"),
            "reason": d.get("reason"), "evidence": d.get("evidence") or {},
            "queryId": d.get("query_id")}


def model_run(fleet: ServiceFleet, rt: ServiceRuntime) -> dict:
    mgr = rt.manager
    prod = mgr.registry.production()
    alarms = [a for _, _, a in rt.scores]
    n_drift = sum(1 for d in mgr.decisions if d.get("action") in ("promote", "rollback", "ask"))
    return {
        "runId": f"{rt.service_id}-v{prod.version}",
        "entityId": rt.service_id,
        "serviceName": rt.display_name,
        "version": prod.version,
        "stage": "STREAMING",
        "modelType": "PCA" if fleet.hst_cfg.detector == "pca" else "HalfSpaceTrees",
        "driftLibrary": "ADWIN",
        "updatedAt": _iso(mgr.registry.transitions[-1].wall_time),
        "params": {
            "nTrees": fleet.hst_cfg.n_trees, "height": fleet.hst_cfg.height,
            "windowSize": fleet.hst_cfg.window_size, "seed": fleet.hst_cfg.seed,
            "adwinDelta": mgr.cfg.adwin_delta,
        },
        "metrics": {
            "rollingMeanScore": round(sum(s for _, s, _ in rt.scores) / max(1, len(rt.scores)), 4),
            "cumulativeDriftCount": n_drift,
            "warnRate": round(sum(alarms) / max(1, len(alarms)), 4),
            "warmUpEvents": fleet.warm_up_rows,
            "warmUpThroughputEps": 0,
            "evalPrecision": 0.0, "evalRecall": 0.0, "evalF1": 0.0,
        },
        # lifecycle extras (frontend ModelRun extension)
        "detector": fleet.hst_cfg.detector + (f" (EWMA {fleet.hst_cfg.smooth_span})" if fleet.hst_cfg.smooth_span else ""),
        "thresholdMethod": mgr.cfg.threshold_method,
        "phase": mgr.phase,
        "productionVersion": prod.version,
        "versionCount": len(mgr.registry.versions),
        "rebaselined": mgr.shifts,
        "openQueries": len(mgr.open_queries),
        "lastDecision": _decision(mgr.decisions[-1]) if mgr.decisions else None,
    }


def model_detail(fleet: ServiceFleet, rt: ServiceRuntime) -> dict:
    return {**model_run(fleet, rt), "versions": model_versions(rt), "transitions": transitions(rt),
            "decisions": decisions(rt), "queries": [q for q in _queries(rt)]}


def _queries(rt: ServiceRuntime) -> list[dict]:
    out = []
    for qid in rt.manager.queries:
        q = rt.manager.public_query(qid)
        out.append({"queryId": q["query_id"], "serviceId": q["service_id"],
                    "serviceName": rt.display_name, "status": q["status"],
                    "question": q["question"], "reason": q["reason"], "evidence": q["evidence"],
                    "createdStep": q["created_step"], "expiresStep": q["expires_step"],
                    "currentStep": rt.manager.step, "answer": q["answer"],
                    "operator": q["operator"]})
    return out


def queries(fleet: ServiceFleet, status: str | None) -> list[dict]:
    rows = [q for rt in fleet.services.values() for q in _queries(rt)]
    return [q for q in rows if status is None or q["status"] == status]
