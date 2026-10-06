# app/api/routes/graph.py
from fastapi import APIRouter, Depends
from app.core.graph_store import GraphStore
from app.core.centrality import CentralityCalculator
from app.core.blast_radius import BlastRadiusAnalyzer

router = APIRouter(prefix="/api/graph", tags=["graph"])
store = GraphStore()

@router.get("/")
def get_graph():
    return store.snapshot()

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
    # trigger Topology Updater -> GraphStore -> Neo4j
    ...