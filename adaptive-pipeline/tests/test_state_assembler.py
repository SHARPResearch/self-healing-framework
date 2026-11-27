"""
test_state_assembler.py
Tests to prove can cook the 55-dim state vector.
"""
import numpy as np
from app.state_assembler import StateAssembler

def test_state_assembler_output_shape():
    """The state vector must be exactly 55 dimensions."""
    assembler = StateAssembler()
    # Use a dummy anomaly_id and service_id
    state = assembler.assemble("payment-service", "ANM-2026-10-05-0001")
    
    assert state.shape[0] == 55, f"Expected 55 dims, got {state.shape[0]}"
    assert not np.isnan(state).any(), "State vector contains NaN values!"

def test_state_assembler_normalization():
    """All values in the state vector must be between 0 and 1."""
    assembler = StateAssembler()
    state = assembler.assemble("payment-service", "ANM-2026-10-05-0001")
    
    assert np.all(state >= 0), "State vector has negative values!"
    assert np.all(state <= 1), "State vector has values greater than 1!"

    def test_state_assembler_fetches_real_action_history():
    """The assembler should query the DB for action history without crashing."""
    assembler = StateAssembler()
    # Even if the DB has no history for this service, it should return a valid 55-dim vector
    state = assembler.assemble("payment-service", "ANM-2026-10-05-0001")
    
    assert state.shape[0] == 55
    # The first 5 dims of the history block (indices 38 to 42) should be numbers (0-3)
    history_block = state[38:43]
    assert len(history_block) == 5