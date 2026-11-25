# services/decision-engine/app/integration/catalog.py
"""
Service catalog resolution.

Component 2 used to index its own hardcoded catalog (`mock_data.SERVICES`) to
answer "does this service exist?" and to give the rule engine a service's
layer / team / namespace. That only works for the service names that catalog
happens to contain, and it raised `KeyError` for anything else — which is every
service on a real cluster (Online Boutique: `frontend`, `cartservice`, …).

`resolve_catalog()` uses the nodes of the live dependency graph (which
Component 1 supplies) as the source of truth. The local demo catalog is only
used when no graph is loaded at all (replay mode / isolated tests).
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.graph_store import GraphStore

log = logging.getLogger(__name__)

#: Defaults for a service we know nothing about beyond its graph node.
_DEFAULTS: dict[str, Any] = {
    "layer": "domain",
    "team": "unknown",
    "runtime": "k8s",
    "version": "unknown",
    "region": "local",
    "node_pool": "default",
    "replicas": 1,
    "criticality": 0.5,
    "health": "healthy",
}


def resolve_catalog() -> dict[str, dict]:
    """
    The live service catalog, derived from the graph Component 1 supplied.

    Cheap enough to call per decision (a dict copy over tens of services); it is
    also called once per ingestion cycle so a service that appears in the
    cluster mid-run is accepted immediately.
    """
    try:
        nodes = list(GraphStore().graph().nodes(data=True))
    except Exception:  # noqa: BLE001 - an empty graph must not break ingestion
        nodes = []

    if not nodes:
        from app.api.routes.mock_data import SERVICES

        log.warning("catalog: graph empty, using the local catalog only")
        return {sid: dict(entry) for sid, entry in SERVICES.items()}

    catalog: dict[str, dict] = {}
    for sid, data in nodes:
        entry: dict[str, Any] = dict(data)
        entry.setdefault("service_id", sid)
        entry.setdefault("display_name", entry.get("name") or sid)
        entry.setdefault("name", entry.get("display_name") or sid)
        entry.setdefault("namespace", "default")
        for key, default in _DEFAULTS.items():
            entry.setdefault(key, default)
        if data.get("criticality") is not None:
            entry["criticality"] = data["criticality"]
        if data.get("health"):
            entry["health"] = data["health"]
        catalog[sid] = entry

    return catalog


def catalog_for_anomaly(anomaly: dict[str, Any]) -> dict[str, dict]:
    """
    Catalog for one anomaly, with a synthesized entry for live services that
    are not in the dependency graph yet.
    """
    catalog = resolve_catalog()
    sid = anomaly.get("service_id")
    if not sid:
        return catalog
    if sid in catalog:
        return catalog

    catalog[sid] = {
        "service_id": sid,
        "display_name": anomaly.get("service_name") or sid,
        "name": anomaly.get("service_name") or sid,
        "namespace": anomaly.get("namespace") or "online-boutique",
        "layer": anomaly.get("layer") or "domain",
        "team": anomaly.get("team") or "platform",
        "runtime": "online-boutique",
        "version": "unknown",
        "region": "local",
        "node_pool": "default",
        "replicas": 1,
        "criticality": 0.5,
        "health": "healthy",
    }
    log.info("catalog: synthesized entry for live service %s", sid)
    return catalog


def known_services() -> set[str]:
    """Service ids the engine will accept an anomaly for."""
    return set(resolve_catalog())
