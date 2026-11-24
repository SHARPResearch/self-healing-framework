# app/core/graph_store.py
from logging import log

from cmath import log

import networkx as nx
from threading import RLock
from app.core.models import ServiceNode, DependencyEdge, DependencyGraph

class GraphStore:
    """Thread-safe in-memory directed dependency graph."""
    _instance: "GraphStore | None" = None
    _lock = RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._g = nx.DiGraph()
            return cls._instance

    # --- Mutations ---------------------------------------------------
    def upsert_node(self, node: ServiceNode) -> None:
        with self._lock:
            self._g.add_node(node.id, **node.model_dump())

    def upsert_edge(self, edge: DependencyEdge) -> None:
        with self._lock:
            self._g.add_edge(edge.source, edge.target,
                             strength=edge.strength,
                             protocol=edge.protocol,
                             **edge.metadata)

    def remove_node(self, node_id: str) -> None:
        with self._lock:
            if self._g.has_node(node_id):
                self._g.remove_node(node_id)

    def clear(self) -> None:
        """Drop every node and edge, for a wholesale topology reload."""
        with self._lock:
            self._g.clear()

    # --- Reads -------------------------------------------------------
    def snapshot(self) -> DependencyGraph:
        with self._lock:
            nodes = []
            for node_id, data in self._g.nodes(data=True):
                # A node can end up in the graph with no attributes if some
                # other code path called add_node(id) bare. Backfill the two
                # required fields from the graph key so pydantic never sees {}.
                payload = dict(data) if data else {}
                payload.setdefault("id", node_id)
                payload.setdefault("name", node_id)
                try:
                    nodes.append(ServiceNode(**payload))
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "graph_store: dropping unparseable node %r: %s",
                        node_id,
                        exc,
                    )
            edges = []
            for u, v, d in self._g.edges(data=True):
                try:
                    edges.append(
                        DependencyEdge(
                            source=u,
                            target=v,
                            strength=d.get("strength", 1.0),
                            protocol=d.get("protocol", "http"),
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "graph_store: dropping unparseable edge %r->%r: %s",
                        u,
                        v,
                        exc,
                    )
        return DependencyGraph(nodes=nodes, edges=edges)
    
    def graph(self) -> nx.DiGraph:
        """Expose read-only; callers must not mutate."""
        return self._g