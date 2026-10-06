# services\decision-engine\app\topology\static_source.py
from pathlib import Path
import yaml
from app.core.graph_store import GraphStore
from app.core.models import ServiceNode, DependencyEdge


def load_static_topology(path: str = "seeds/topology.yaml") -> None:
    """Load nodes and edges from a YAML file into the in-memory graph."""
    p = Path(path)
    if not p.exists():
        print(f"⚠️  seed file not found: {p.resolve()}")
        return

    data = yaml.safe_load(p.read_text()) or {}
    store = GraphStore()

    for n in data.get("nodes", []):
        store.upsert_node(ServiceNode(**n))

    for e in data.get("edges", []):
        store.upsert_edge(DependencyEdge(**e))

    print(f"   loaded {len(data.get('nodes', []))} nodes, "
          f"{len(data.get('edges', []))} edges")