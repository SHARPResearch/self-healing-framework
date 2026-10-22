"""
Tests for the Mock Prometheus Data Generator.
Ensures generated payloads are valid and can be parsed by the Schema.
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


def test_mock_data_generation_memory_leak():
    """Test that memory leak scenario generates valid JSON and passes schema."""
    json_str = MockPrometheusGenerator.get_json_string("memory_leak")
    payload_dict = json.loads(json_str)
    
    # Parse through Pydantic Schema
    payload = EnrichedContextPayload(**payload_dict)
    
    assert payload.prediction_data.failure_type.value == "MEMORY_LEAK"
    assert payload.prediction_data.failure_probability == 0.88
    
    # Ensure it converts to state vector successfully
    state = assemble_state_vector(payload)
    assert state.shape == (7,)


def test_mock_data_generation_high_latency():
    """Test high latency scenario with guardrails active."""
    json_str = MockPrometheusGenerator.get_json_string("high_latency")
    payload_dict = json.loads(json_str)
    
    payload = EnrichedContextPayload(**payload_dict)
    
    assert payload.prediction_data.failure_type.value == "HIGH_LATENCY"
    assert payload.guardrail_status.cooldown_active == True
    
    state = assemble_state_vector(payload)
    assert state[6] == 1.0  # Cooldown active should be 1.0 in state vector


def test_mock_data_generation_default():
    """Test default/healthy scenario."""
    json_str = MockPrometheusGenerator.get_json_string("healthy")
    payload_dict = json.loads(json_str)
    
    payload = EnrichedContextPayload(**payload_dict)
    assert payload.prediction_data.failure_probability == 0.10