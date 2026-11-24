# services/decision-engine/app/integration/topology.py
"""
Dependency graph from Component 1.

The Component 2 report treats the graph as an *input* ("Graph Query"), not as
something the engine owns. Component 1 is the component that sees the whole
fleet, so it serves the topology at `GET /api/topology` and this module loads it
into the local `GraphStore` — the same store that centrality and blast-radius
are computed from, so everything downstream follows automatically.

If Component 1 is unreachable (it may start after this engine) the seeded
topology is loaded instead, and the refresh job upgrades the graph as soon as
Component 1 answers. That keeps boot order irrelevant.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.core.graph_store import GraphStore
from app.core.models import DependencyEdge, ServiceNode

log = logging.getLogger(__name__)

#: Where the currently loaded graph came from: "component1" or "seed".
TOPOLOGY_SOURCE: str = "unloaded"
#: Component 1's content hash for the graph, for change detection.
TOPOLOGY_VERSION: str | None = None

SEED_PATH = "seeds/topology.yaml"


def _base_url() -> str:
    return (getattr(settings, "COMPONENT1_URL", "") or "http://localhost:8002").rstrip("/")


async def fetch_topology(timeout: float = 3.0) -> dict[str, Any] | None:
    """`GET /api/topology`. None when Component 1 is unavailable."""
    url = f"{_base_url()}/api/topology"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001 - integration must never break boot
        log.warning("Component 1 topology unavailable at %s: %s", url, exc)
        return None

    if not isinstance(payload, dict) or not payload.get("nodes"):
        log.warning("Component 1 /api/topology returned an unusable payload")
        return None
    return payload


# def _apply(payload: dict[str, Any]) -> None:
#     """Replace the in-memory graph with the payload's nodes and edges."""
#     store = GraphStore()
#     store.clear()

#     for node in payload.get("nodes", []):
#         try:
#             store.upsert_node(ServiceNode(**node))
#         except Exception:  # noqa: BLE001 - one malformed node must not abort the load
#             log.warning("topology: skipping malformed node %r", node.get("id"))

#     for edge in payload.get("edges", []):
#         try:
#             store.upsert_edge(DependencyEdge(**edge))
#         except Exception:  # noqa: BLE001
#             log.warning("topology: skipping malformed edge %r", edge)

#     log.info(
#         "topology: loaded %d nodes / %d edges from %s",
#         store.graph().number_of_nodes(),
#         store.graph().number_of_edges(),
#         "Component 1",
#     )

def _apply(payload: dict[str, Any]) -> None:
    """Replace the in-memory graph with the payload's nodes and edges."""
    store = GraphStore()
    store.clear()

    total = 0
    accepted = 0
    for node in payload.get("nodes", []):
        total += 1
        try:
            store.upsert_node(ServiceNode(**node))
            accepted += 1
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "topology: skipping malformed node %r: %s",
                node.get("id") or node.get("service") or node,
                exc,
            )

    for edge in payload.get("edges", []):
        try:
            store.upsert_edge(DependencyEdge(**edge))
        except Exception as exc:  # noqa: BLE001
            log.warning("topology: skipping malformed edge %r: %s", edge, exc)

    if total and accepted == 0:
        # Every node rejected -> this is a schema mismatch, not a data glitch.
        # Fail the load so load_topology() falls back to the seed instead of
        # leaving a half-empty graph that crashes snapshot() later.
        raise RuntimeError(
            f"topology: 0/{total} nodes accepted from Component 1 — "
            f"ServiceNode schema mismatch (check C1 /api/topology vs models.ServiceNode)"
        )

    log.info(
        "topology: loaded %d/%d nodes / %d edges from Component 1",
        accepted,
        total,
        store.graph().number_of_edges(),
    )


def _load_seed() -> None:
    from app.topology.sources.static_source import load_static_topology

    load_static_topology(SEED_PATH)


# async def load_topology(force: bool = False) -> str:
#     """
#     Load the graph, preferring Component 1. Returns the source actually used.

#     `force` skips the "nothing changed" shortcut, used by the refresh endpoint.
#     """
#     global TOPOLOGY_SOURCE, TOPOLOGY_VERSION

#     payload = await fetch_topology()
#     if payload:
#         version = str(payload.get("version") or "")
#         if not force and TOPOLOGY_SOURCE == "component1" and version == TOPOLOGY_VERSION:
#             return TOPOLOGY_SOURCE
#         _apply(payload)
#         TOPOLOGY_SOURCE = "component1"
#         TOPOLOGY_VERSION = version
#         return TOPOLOGY_SOURCE

#     if TOPOLOGY_SOURCE == "component1":
#         # Never downgrade a graph that is already live just because one refresh
#         # failed; a transient blip must not empty the dependency context.
#         log.warning("topology: refresh failed, keeping the Component 1 graph")
#         return TOPOLOGY_SOURCE

#     _load_seed()
#     TOPOLOGY_SOURCE = "seed"
#     TOPOLOGY_VERSION = None
#     return TOPOLOGY_SOURCE

async def load_topology(force: bool = False) -> str:
    global TOPOLOGY_SOURCE, TOPOLOGY_VERSION

    payload = await fetch_topology()
    if payload:
        version = str(payload.get("version") or "")
        if not force and TOPOLOGY_SOURCE == "component1" and version == TOPOLOGY_VERSION:
            return TOPOLOGY_SOURCE
        try:
            _apply(payload)
            TOPOLOGY_SOURCE = "component1"
            TOPOLOGY_VERSION = version
            return TOPOLOGY_SOURCE
        except Exception as exc:
            log.error("topology: Component 1 payload unusable (%s) — falling back to seed", exc)

    if TOPOLOGY_SOURCE == "component1":
        log.warning("topology: refresh failed, keeping the Component 1 graph")
        return TOPOLOGY_SOURCE

    _load_seed()
    TOPOLOGY_SOURCE = "seed"
    TOPOLOGY_VERSION = None
    return TOPOLOGY_SOURCE


async def refresh_topology() -> str:
    return await load_topology(force=True)


def start_topology_refresh(scheduler) -> None:
    """Re-read Component 1's topology periodically (topology changes over time)."""
    scheduler.add_job(
        refresh_topology,
        "interval",
        seconds=60,
        id="topology_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("Topology refresh scheduled (every 60s, source=Component 1)")
