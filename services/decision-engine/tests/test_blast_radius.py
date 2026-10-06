# tests/test_blast_radius.py
import networkx as nx
from app.core.graph_store import GraphStore
from app.core.blast_radius import BlastRadiusAnalyzer
from app.core.models import ServiceNode, DependencyEdge

def _seed():
    s = GraphStore()
    for n in ["auth", "orders", "inventory", "payment", "api"]:
        s.upsert_node(ServiceNode(id=n, name=n))
    for a, b in [("orders","auth"), ("orders","inventory"),
                 ("payment","orders"), ("api","payment"), ("api","orders")]:
        s.upsert_edge(DependencyEdge(source=a, target=b))
    return s

def test_blast_radius_of_auth():
    s = _seed()
    an = BlastRadiusAnalyzer(s)
    # auth is depended on by orders -> payment -> api
    assert an.reverse_reachable("auth") == {"orders", "payment", "api"}
    assert an.size("auth") == 3

def test_blast_radius_of_leaf():
    s = _seed()
    an = BlastRadiusAnalyzer(s)
    assert an.size("api") == 0