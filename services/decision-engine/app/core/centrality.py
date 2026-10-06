# app/core/centrality.py
import networkx as nx
from app.core.graph_store import GraphStore

class CentralityCalculator:
    """
    Produces centrality weight in [1, 2] per your Severity Calculator spec.
    Higher centrality => more critical service.
    """

    def __init__(self, store: GraphStore):
        self.store = store

    def compute(self) -> dict[str, float]:
        g = self.store.graph()
        if g.number_of_nodes() == 0:
            return {}

        # Blend in-degree (who depends on me) with betweenness
        indeg = nx.in_degree_centrality(g)               # 0..1
        between = nx.betweenness_centrality(g, normalized=True)

        blended = {
            n: 0.7 * indeg.get(n, 0) + 0.3 * between.get(n, 0)
            for n in g.nodes
        }

        # Normalize to [1, 2]
        if not blended:
            return {}
        lo, hi = min(blended.values()), max(blended.values())
        span = (hi - lo) or 1.0
        return {n: 1.0 + (v - lo) / span for n, v in blended.items()}