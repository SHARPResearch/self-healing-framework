"""
gcn_embedder.py
The "Whisper Network" for Component 3.
Uses PyTorch Geometric (PyG) to read the dependency graph and create 
32-dimensional embeddings for every microservice.
"""
import os
import yaml
import torch
import torch.nn.functional as F
from torch_geometric.nn import GCNConv
from torch_geometric.data import Data
from .config import settings

# Map health status to a number so the math works
HEALTH_MAP = {
    "healthy": 1.0,
    "degraded": 0.5,
    "down": 0.0,
    "watch": 0.75,
    "critical": 0.25
}

class SimpleGCN(torch.nn.Module):
    """
    The actual Whisper Network. 
    It takes node features and edges, and passes messages between them.
    """
    def __init__(self, num_node_features, embedding_dim):
        super(SimpleGCN, self).__init__()
        # Layer 1: Whisper to immediate neighbors
        self.conv1 = GCNConv(num_node_features, 64)
        # Layer 2: Whisper to neighbors-of-neighbors
        self.conv2 = GCNConv(64, embedding_dim)

    def forward(self, x, edge_index):
        # x = node features, edge_index = who is holding hands
        x = self.conv1(x, edge_index)
        x = F.relu(x)  # Activate the neurons
        x = F.dropout(x, p=0.2, training=self.training) # Prevent overfitting
        x = self.conv2(x, edge_index)
        return x

class GCNEmbedder:
    def __init__(self, topology_path: str = None, embedding_dim: int = 32):
        self.embedding_dim = embedding_dim
        self.model = None
        self.node_map = {}  # Maps service_id to index (0 to 15)
        self.data = None
        self.embedding_cache = {}  # The Prep Station (Cache)
        
        # Build the graph from Liyana's topology.yaml
        self._build_graph(topology_path)
        self._initialize_model()

    def _build_graph(self, topology_path: str = None):
        """Reads the canonical dependency graph and converts it to PyG format."""
        # 1. Default = the official graph owned by Component 2 (configurable via .env)
        rel_path = topology_path or settings.topology_path

        # 2. repo root = two folders up from this file (adaptive-pipeline/app -> repo root)
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        full_path = os.path.join(repo_root, rel_path.replace('/', os.sep))

        if not os.path.exists(full_path):
            raise FileNotFoundError(
                f"Dependency graph not found at:\n  {full_path}\n"
                f"Set TOPOLOGY_PATH in .env to the correct location "
                f"(default: services/decision-engine/seeds/topology.yaml)."
            )

        with open(full_path, 'r') as f:
            topology = yaml.safe_load(f)

        nodes = topology['nodes']
        edges = topology['edges']

        # 1. Create Node Features (2 dimensions: criticality, health)
        node_features = []
        for i, node in enumerate(nodes):
            self.node_map[node['id']] = i
            criticality = node.get('criticality', 0.5)
            health = HEALTH_MAP.get(node.get('health', 'healthy'), 1.0)
            node_features.append([criticality, health])
        
        x = torch.tensor(node_features, dtype=torch.float)

        # 2. Create Edge Index (PyG requires [2, num_edges] format)
        edge_indices = []
        for edge in edges:
            src_idx = self.node_map.get(edge['source'])
            tgt_idx = self.node_map.get(edge['target'])
            if src_idx is not None and tgt_idx is not None:
                edge_indices.append([src_idx, tgt_idx])
                edge_indices.append([tgt_idx, src_idx]) # Make it bidirectional!
        
        edge_index = torch.tensor(edge_indices, dtype=torch.long).t().contiguous()

        # 3. Create PyG Data Object
        self.data = Data(x=x, edge_index=edge_index)

    def _initialize_model(self):
        """Creates the GCN model."""
        num_features = self.data.x.shape[1] # Should be 2
        self.model = SimpleGCN(num_features, self.embedding_dim)
        self.model.eval() # Set to evaluation mode

    def get_embedding(self, service_id: str) -> torch.Tensor:
        """Returns the 32-dim whisper summary for a specific service."""
        # 1. Check the Prep Station first!
        if service_id in self.embedding_cache:
            return self.embedding_cache[service_id]
            
        if service_id not in self.node_map:
            return torch.zeros(self.embedding_dim)
            
        with torch.no_grad():
            embeddings = self.model(self.data.x, self.data.edge_index)
            node_idx = self.node_map[service_id]
            result = embeddings[node_idx]
            
            # 2. Put the fresh spice in the jar for next time!
            self.embedding_cache[service_id] = result
            return result

# Quick test if run directly
if __name__ == "__main__":
    embedder = GCNEmbedder()
    emb = embedder.get_embedding("payment-service")
    print(f"Payment Service Embedding Shape: {emb.shape}")
    print(f"First 5 numbers: {emb[:5]}")