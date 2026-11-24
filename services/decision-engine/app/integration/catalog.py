# services/decision-engine/app/integration/catalog.py
"""
Service catalog resolution.

Component 2 used to index its own hardcoded catalog (`mock_data.SERVICES`) to
answer "does this service exist?" and to give the rule engine a service's
layer / team / namespace. That only works for the service names that catalog
happens to contain, and it raised `KeyError` for anything else — which is every
service on a real cluster (Online Boutique: `frontend`, `cartservice`, …).

`resolve_catalog()` merges:

  1. the local catalog (replay mode / demo scenarios),
  2. the nodes of the live dependency graph (which Component 1 supplies),

into one dict with the keys `ContextBuilder` and the rules read. Unknown
services therefore work too: the graph node supplies id, name, namespace and
criticality, and generic defaults cover the rest.
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
    The full service catalog: local entries plus every graph node.

    Cheap enough to call per decision (a dict copy over tens of services); it is
    also called once per ingestion cycle so a service that appears in the
    cluster mid-run is accepted immediately.
    """
    from app.api.routes.mock_data import SERVICES

    catalog: dict[str, dict] = {sid: dict(entry) for sid, entry in SERVICES.items()}

    try:
        nodes = GraphStore().graph().nodes(data=True)
    except Exception:  # noqa: BLE001 - an empty graph must not break ingestion
        log.warning("catalog: graph unavailable, using the local catalog only")
        return catalog

    for sid, data in nodes:
        entry = catalog.setdefault(sid, {})
        entry.setdefault("service_id", sid)
        entry.setdefault("display_name", data.get("name") or sid)
        entry.setdefault("namespace", data.get("namespace") or "default")
        for key, default in _DEFAULTS.items():
            entry.setdefault(key, default)
        if data.get("criticality") is not None:
            entry["criticality"] = data["criticality"]
        if data.get("health"):
            entry["health"] = data["health"]

    return catalog


def known_services() -> set[str]:
    """Service ids the engine will accept an anomaly for."""
    return set(resolve_catalog())
