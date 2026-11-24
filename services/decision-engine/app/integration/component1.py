# services/decision-engine/app/integration/component1.py
"""
Read-only client for Component 1 — the ml-backend anomaly detector and dynamic
model-updating service (owner: Member 2). Component 2 never writes to it.

One contract, two callers:

  * `ingestion/anomaly_sink.py` turns a per-service state into an anomaly signal
    (so anomalies originate from Component 1's detector instead of the local
    mock health table),
  * `decision/job.py` attaches the same state to the decision context, so every
    decision records the model version and the drift / quarantine phase it was
    made under.

Component 1's own view of a service (`GET /api/services`) is:

    {serviceId, displayName, status, anomalyScore, scoreHistory, lastAction,
     lastActionAt, driftDetected, phase, quarantineTrigger, quarantine, alarm,
     modelVersion, openQueries, smdEntity, source}

`status` uses the shared severity vocabulary documented in
`frontend/src/shared/types.ts`: <0.5 watch, 0.5-0.7 warn, 0.7-0.85 degrade,
>0.85 critical.

Everything here degrades: if Component 1 is unreachable the caller falls back to
its previous behaviour rather than stalling the pipeline.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

# Component 1 severity -> the anomaly_events.severity vocabulary Component 2 stores.
SEVERITY_MAP = {"warn": "low", "degrade": "medium", "critical": "high"}

#: Scores below this are "watch" and are not treated as an anomaly (shared threshold).
ANOMALY_THRESHOLD = 0.5


def _base_url() -> str:
    return (getattr(settings, "COMPONENT1_URL", "") or "http://localhost:8002").rstrip("/")


async def fetch_services(timeout: float = 3.0) -> list[dict[str, Any]]:
    """`GET /api/services`. Returns [] (and logs) when Component 1 is unavailable."""
    url = f"{_base_url()}/api/services"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001 - integration must never raise into the pipeline
        log.warning("Component 1 unreachable at %s: %s", url, exc)
        return []

    if not isinstance(payload, list):
        log.warning("Component 1 /api/services returned %s, expected a list", type(payload).__name__)
        return []
    return [row for row in payload if isinstance(row, dict)]


def by_service(states: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(s.get("serviceId")): s for s in states if s.get("serviceId")}


def is_unhealthy(state: dict[str, Any]) -> bool:
    """
    Component 1 already ran its detector; trust its alarm flag first, then fall
    back to the severity band so a state that crossed a band but not the alarm
    threshold still counts.
    """
    if state.get("alarm"):
        return True
    try:
        score = float(state.get("anomalyScore") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    if score >= ANOMALY_THRESHOLD:
        return True
    return str(state.get("status") or "").lower() in SEVERITY_MAP


def component1_context(state: dict[str, Any]) -> dict[str, Any]:
    """The slice of Component 1's state worth storing on a decision."""
    return {
        "model_version": state.get("modelVersion"),
        "phase": state.get("phase"),
        "drift_detected": bool(state.get("driftDetected")),
        "quarantine_trigger": state.get("quarantineTrigger"),
        "quarantine": state.get("quarantine"),
        "open_queries": state.get("openQueries"),
        "status": state.get("status"),
        "anomaly_score": state.get("anomalyScore"),
        "smd_entity": state.get("smdEntity"),
    }


def anomaly_from_state(
    state: dict[str, Any],
    incident_id: str,
    detected_at: datetime,
) -> dict[str, Any]:
    """
    Build the `anomaly_events` row from Component 1's state.

    Component 1 reports a score and a severity band, not a single offending
    metric — the detector is multivariate — so `metric` is `anomaly_score` and
    `actual_value` is the score itself. The model version travels with the
    anomaly and ends up on the decision, which is what lets the dashboard show
    "this decision was made against model vN".
    """
    try:
        score = float(state.get("anomalyScore") or 0.0)
    except (TypeError, ValueError):
        score = 0.0

    band = str(state.get("status") or "").lower()
    severity = SEVERITY_MAP.get(band, "medium")

    return {
        "id": incident_id,
        "service_id": state.get("serviceId"),
        "service_name": state.get("displayName"),
        "team": None,
        "layer": None,
        "anomaly_score": round(score, 4),
        "severity": severity,
        "metric": "anomaly_score",
        "actual_value": round(score, 4),
        "expected_value": ANOMALY_THRESHOLD,
        "deviation_sigma": None,
        "confidence": round(score, 4),
        "model_version": (
            str(state["modelVersion"]) if state.get("modelVersion") is not None else None
        ),
        "features": component1_context(state),
        "detected_at": detected_at,
    }
