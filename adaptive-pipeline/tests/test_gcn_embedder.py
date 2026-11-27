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

def test_gcn_embedding_cache():
    """The embedder should cache results to prevent redundant graph computation."""
    embedder = GCNEmbedder()
    
    # First call: Computes the embedding and puts it in the cache
    emb1 = embedder.get_embedding("payment-service")
    assert len(embedder.embedding_cache) == 1, "Cache should have 1 item after first call"
    
    # Second call: Should use the cache, not recompute
    emb2 = embedder.get_embedding("payment-service")
    assert len(embedder.embedding_cache) == 1, "Cache size should not grow for duplicate requests"
    assert torch.equal(emb1, emb2), "Cached embedding should match the original"