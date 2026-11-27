"""Tests to prove our GCN Whisper Network reads the real graph."""
from app.gcn_embedder import GCNEmbedder

def test_gcn_loads_topology_correctly():
    embedder = GCNEmbedder()                      # uses config default path
    assert len(embedder.node_map) == 16, "Expected 16 microservices in topology!"

def test_gcn_output_shape_is_32_dim():
    embedder = GCNEmbedder()
    embedding = embedder.get_embedding("payment-service")
    assert embedding.shape[0] == 32, f"Expected 32 dims, got {embedding.shape[0]}"
    assert not embedding.isnan().any(), "Embedding contains NaN values!"

def test_gcn_handles_unknown_service():
    embedder = GCNEmbedder()
    embedding = embedder.get_embedding("fake-service-xyz")
    assert embedding.shape[0] == 32
    assert embedding.sum().item() == 0.0, "Fallback should be all zeros"