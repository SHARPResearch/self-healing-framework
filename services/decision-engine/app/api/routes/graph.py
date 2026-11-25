# app/api/routes/graph.py
from fastapi import APIRouter, Depends
from app.core.graph_store import GraphStore
from app.core.centrality import CentralityCalculator
from app.core.blast_radius import BlastRadiusAnalyzer

router = APIRouter(prefix="/api/graph", tags=["graph"])
store = GraphStore()

@router.get("/")
async def get_graph():
    from app.integration import topology as topology_integration

    source = await topology_integration.refresh_topology()
    snapshot = store.snapshot()
    return {
        **snapshot.model_dump(),
        "source": source,
        "node_source": getattr(topology_integration, "TOPOLOGY_NODE_SOURCE", source),
        "edge_source": getattr(topology_integration, "TOPOLOGY_EDGE_SOURCE", "seed"),
        "version": topology_integration.TOPOLOGY_VERSION,
    }

@router.get("/centrality")
def get_centrality():
    return CentralityCalculator(store).compute()

@router.get("/blast-radius/{service_id}")
def get_blast_radius(service_id: str):
    an = BlastRadiusAnalyzer(store)
    return {
        "service": service_id,
        "reverse_reachable": list(an.reverse_reachable(service_id)),
        "size": an.size(service_id),
        "factor": an.factor(service_id),
    }

@router.post("/refresh")
async def refresh_topology():
    """Re-read the topology from Component 1 (falls back to the seed)."""
    from app.integration import topology as topology_integration

    source = await topology_integration.refresh_topology()
    snapshot = store.snapshot()
    return {
        "ok": True,
        "source": source,
        "version": topology_integration.TOPOLOGY_VERSION,
        "nodes": len(snapshot.nodes),
        "edges": len(snapshot.edges),
    }


@router.get("/source")
def get_source():
    """Where the graph came from: Component 1 or the local seed."""
    from app.integration import topology as topology_integration

    snapshot = store.snapshot()
    return {
        "source": topology_integration.TOPOLOGY_SOURCE,
        "node_source": topology_integration.TOPOLOGY_NODE_SOURCE,
        "edge_source": topology_integration.TOPOLOGY_EDGE_SOURCE,
        "version": topology_integration.TOPOLOGY_VERSION,
        "nodes": len(snapshot.nodes),
        "edges": len(snapshot.edges),
    }