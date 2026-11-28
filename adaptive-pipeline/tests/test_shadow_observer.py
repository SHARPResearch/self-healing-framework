"""
test_shadow_observer.py
Tests to prove our Time Machine correctly processes shadow records from the DB.
"""
from app.shadow_observer import ShadowObserver

def test_shadow_observer_processes_real_db_records():
    """The observer should fetch records from the DB and return calculated rewards."""
    observer = ShadowObserver()
    results = observer.process_shadow_records(limit=10)
    
    # We know Liyana's DB has 97 shadow records, so we should get some back
    assert len(results) > 0, "Expected to fetch shadow records from the DB"
    
    # Verify the structure of the returned data
    first_result = results[0]
    assert "shadow_id" in first_result
    assert "counterfactual_reward" in first_result
    assert isinstance(first_result["counterfactual_reward"], float)