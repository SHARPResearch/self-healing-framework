# services/decision-engine/app/integration/telemetry.py
"""
Infra / app telemetry for the decision context.

Priority:
  1. the snapshots this engine captured for the anomaly — `infra_snapshots` and
     `app_snapshots` in Timescale, whose `raw` column holds the exact payload the
     puller received at capture time;
  2. neutral telemetry for the live topology (or the local generator in replay
      mode), so an anomaly with no snapshots still gets a decision.

This is the honest path to real numbers: `TELEMETRY_SOURCE_URL` decides where
`ingestion/telemetry_puller.py` reads from, so pointing it at the live scrape
makes severity, blast radius and the rule conditions run on real measurements
without touching this module. The `source` return value records which one was
used, and it is stored on the decision so the dashboard can show it.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.persistence.timescale import timescale_store

log = logging.getLogger(__name__)


def _mock_telemetry(service_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Fallback values from the local generator.

    Imported lazily: `app.api.routes.decisions` imports this module, and
    `mock_data` lives under `app.api`, whose package `__init__` imports the
    routes — a module-level import here closes that loop.
    """
    from app.api.routes.mock_data import _app, _infra

    return _infra(service_id), _app(service_id)


def _neutral_telemetry(service_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Neutral payload for a service the generator does not know.

    This is the live-cluster path: Online Boutique's `frontend` is not in the
    demo catalog, so instead of raising `KeyError` we hand the context an
    empty-but-well-formed reading. Rules that need a metric it lacks simply
    do not match; rules based on score / classification / blast radius — the
    generic set — still fire.
    """
    entry: dict[str, Any] = {}
    try:
        from app.integration.catalog import resolve_catalog

        entry = resolve_catalog().get(service_id, {})
    except Exception:  # noqa: BLE001
        pass

    name = entry.get("display_name") or service_id
    infra = {
        "service_id": service_id,
        "service_name": name,
        "layer": entry.get("layer"),
        "team": entry.get("team"),
        "namespace": entry.get("namespace"),
        "node": None,
        "pod_count": entry.get("replicas"),
        "ready_pods": entry.get("replicas"),
        "cpu": {},
        "memory": {},
        "network": {},
        "disk": {},
        "gc": {},
    }
    app = {
        "service_id": service_id,
        "service_name": name,
        "layer": entry.get("layer"),
        "team": entry.get("team"),
        "latency_ms": {},
        "status_codes": {},
        "requests_per_sec": None,
        "error_rate": None,
    }
    return infra, app


def _live_topology() -> bool:
    try:
        from app.integration.topology import TOPOLOGY_SOURCE

        return TOPOLOGY_SOURCE == "component1"
    except Exception:  # noqa: BLE001
        return False


def _fallback_telemetry(service_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if _live_topology():
        return _neutral_telemetry(service_id)
    try:
        return _mock_telemetry(service_id)
    except KeyError:
        log.debug("No generated profile for %s — using neutral telemetry", service_id)
        return _neutral_telemetry(service_id)


def _decode(raw: Any) -> dict[str, Any] | None:
    """The `raw` column is JSON text (asyncpg returns JSONB as str)."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return None
    return raw if isinstance(raw, dict) else None


def _latest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Snapshots come back ordered by time ASC and a decision needs one reading.
    The newest captured window edge is used: it is the closest observation to
    the moment the engine decided.
    """
    for row in reversed(rows or []):
        payload = _decode(row.get("raw"))
        if payload:
            return payload
    return None


async def load_snapshots(anomaly_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (infra_payload, app_payload) parsed from the captured snapshots."""
    if not anomaly_id:
        return None, None
    try:
        infra_rows = await timescale_store.get_infra_snapshots(anomaly_id)
        app_rows = await timescale_store.get_app_snapshots(anomaly_id)
    except Exception as exc:  # noqa: BLE001 - telemetry must never stall a decision
        log.warning("snapshot read failed for %s: %s", anomaly_id, exc)
        return None, None

    return _latest(infra_rows), _latest(app_rows)


async def build_telemetry(
    anomaly_id: str,
    service_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """
    Infra + app telemetry for the decision context.

    Returns `(infra, app, source)` where `source` is e.g.
    `{"infra": "snapshot", "app": "mock"}` — recorded so the decision says which
    numbers it was actually made on.
    """
    infra_snapshot, app_snapshot = await load_snapshots(anomaly_id)

    fallback_source = "neutral" if _live_topology() else "mock"
    source = {
        "infra": "snapshot" if infra_snapshot else fallback_source,
        "app": "snapshot" if app_snapshot else fallback_source,
    }

    if not infra_snapshot:
        log.debug("No infra snapshot for %s — falling back to %s values", anomaly_id, fallback_source)
    if not app_snapshot:
        log.debug("No app snapshot for %s — falling back to %s values", anomaly_id, fallback_source)

    if infra_snapshot and app_snapshot:
        return infra_snapshot, app_snapshot, source

    mock_infra, mock_app = _fallback_telemetry(service_id)
    return (
        infra_snapshot or mock_infra,
        app_snapshot or mock_app,
        source,
    )
