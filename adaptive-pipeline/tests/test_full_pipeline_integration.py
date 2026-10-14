
"""
End-to-End Integration Test for the Adaptive Pipeline.
Proves that Mock Data -> Schema -> State Assembler -> DQN Inference works seamlessly.
"""

import sys
import os
import json

# Add root directory to path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from src.mock_prometheus_data import MockPrometheusGenerator
from src.schema import EnrichedContextPayload
from src.state_assembler import assemble_state_vector
from src.dqn_policy_engine import DQN, get_optimal_action, RecoveryAction


def test_full_pipeline_memory_leak_scenario():
    """Test the complete data flow from mock generation to DQN action output."""
    # 1. Generate Mock Input
    json_str = MockPrometheusGenerator.get_json_string("memory_leak")
    payload_dict = json.loads(json_str)
    
    # 2. Schema Validation
    payload = EnrichedContextPayload(**payload_dict)
    assert payload.prediction_data.failure_type.value == "MEMORY_LEAK"
    
    # 3. State Assembly
    state_vector = assemble_state_vector(payload)
    assert state_vector.shape == (7,)
    assert state_vector.dtype.name == "float32"
    
    # 4. DQN Inference
    model = DQN(state_dim=7, action_dim=4)
    action, q_value = get_optimal_action(state_vector, model)
    
    # 5. Validate Output
    assert isinstance(action, RecoveryAction)
    assert isinstance(q_value, float)
    
    print(f"\n✅ Full Pipeline Integration Test Passed!")
    print(f"   Input: Memory Leak (Prob: {payload.prediction_data.failure_probability})")
    print(f"   State Vector: {state_vector}")
    print(f"   Output Action: {action.value} (Q-Value: {q_value:.4f})")