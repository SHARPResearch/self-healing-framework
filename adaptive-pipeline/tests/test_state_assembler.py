"""
test_state_assembler.py
Tests to prove our Master Chef can cook the 55-dim state vector.
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