import pytest

from app.api.routes import graph as graph_routes
from app.core.graph_store import GraphStore
from app.integration import topology


@pytest.fixture(autouse=True)
def clean_graph():
    GraphStore().graph().clear()
    yield
    GraphStore().graph().clear()


@pytest.mark.asyncio
async def test_load_topology_records_component1_source(monkeypatch):
    payload = {
        "version": "abc123",
        "mode": "live",
        "node_source": "live-deployments",
        "edge_source": "istio",
        "nodes": [
            {
                "id": "frontend",
                "name": "Frontend",
                "namespace": "online-boutique",
                "criticality": 1.0,
                "health": "degrade",
            },
            {
                "id": "adservice",
                "name": "Ad Service",
                "namespace": "online-boutique",
                "criticality": 0.55,
                "health": "healthy",
            },
        ],
        "edges": [
            {
                "source": "frontend",
                "target": "adservice",
                "strength": 0.7,
                "protocol": "grpc",
            }
        ],
    }

    async def fake_fetch(timeout=3.0):
        return payload

    monkeypatch.setattr(topology, "fetch_topology", fake_fetch)

    source = await topology.load_topology(force=True)

    assert source == "component1"
    assert topology.TOPOLOGY_NODE_SOURCE == "live-deployments"
    assert topology.TOPOLOGY_EDGE_SOURCE == "istio"
    assert GraphStore().graph().nodes["frontend"]["health"] == "degraded"


@pytest.mark.asyncio
async def test_graph_route_exposes_topology_source(monkeypatch):
    async def fake_refresh(force=False):
        topology.TOPOLOGY_SOURCE = "component1"
        topology.TOPOLOGY_NODE_SOURCE = "live-deployments"
        topology.TOPOLOGY_EDGE_SOURCE = "catalog"
        topology.TOPOLOGY_VERSION = "abc123"
        return "component1"

    monkeypatch.setattr(topology, "refresh_topology", fake_refresh)

    data = await graph_routes.get_graph()

    assert data["source"] == "component1"
    assert data["node_source"] == "live-deployments"
    assert data["edge_source"] == "catalog"
    assert data["version"] == "abc123"
