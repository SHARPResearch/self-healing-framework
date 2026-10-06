# app/core/blast_radius.py
import networkx as nx
from app.core.graph_store import GraphStore

class BlastRadiusAnalyzer:
    def __init__(self, store: GraphStore):
        self.store = store

    def reverse_reachable(self, service_id: str) -> set[str]:
        """All services that (transitively) depend on `service_id`."""
        g = self.store.graph()
        if service_id not in g:
            return set()
        return nx.ancestors(g, service_id)   # ancestors in DiGraph = reverse-reachable

    def size(self, service_id: str) -> int:
        return len(self.reverse_reachable(service_id))

    def weighted(self, service_id: str, criticality: dict[str, float]) -> float:
        g = self.store.graph()
        total = 0.0
        for v in self.reverse_reachable(service_id):
            strength = g.edges[v, service_id].get("strength", 1.0) \
                       if g.has_edge(v, service_id) else 1.0
            total += criticality.get(v, 1.0) * strength
        return total

    def factor(self, service_id: str) -> float:
        """Map blast radius size to [1.0, 1.5] per doc Section 5.6."""
        n = self.size(service_id)
        # log scale so 1000-node graphs still land in range
        import math
        return 1.0 + 0.5 * min(1.0, math.log10(n + 1) / 2.0)