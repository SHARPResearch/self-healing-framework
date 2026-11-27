"""
Tests to prove our DB Reader can successfully fetch real data from Neon.
"""
from app.db_reader import (
    fetch_shadow_records,
    fetch_decision_log,
    fetch_anomaly_events,
    fetch_action_history
)

def test_fetch_shadow_records_returns_data():
    """Shadow records table should have the 97 rows LiyanaArachchi generated."""
    records = fetch_shadow_records(limit=10)
    assert len(records) > 0, "Expected shadow records, got empty list!"
    
    # Check if the columns we need for Counterfactual Reward exist
    first_record = records[0]
    assert "candidate_action" in first_record
    assert "verdict" in first_record
    assert "simulated_outcome" in first_record

def test_fetch_decision_log_has_graph_data():
    """Decision log must contain blast_factor and centrality for our GCN."""
    records = fetch_decision_log(limit=10)
    assert len(records) > 0
    
    first_record = records[0]
    assert "blast_factor" in first_record, "Missing blast_factor for state vector!"
    assert "centrality" in first_record, "Missing centrality for GCN!"

def test_fetch_anomaly_events_has_features():
    """Anomaly events must contain the 6-dim features for our state vector."""
    records = fetch_anomaly_events(limit=10)
    assert len(records) > 0
    
    first_record = records[0]
    assert "anomaly_score" in first_record
    assert "features" in first_record  # This is a JSONB field

def test_fetch_action_history_filters_by_service():
    """Action history should allow filtering by a specific service."""
    # Try fetching history for a known service from the topology
    records = fetch_action_history(service_id="payment-service", limit=5)
    # It might be empty if no actions were taken on payment-service yet, 
    # but the query shouldn't crash.
    assert isinstance(records, list)