"""
Verifies schema parsing, default handling, and state vector transformation.
Designed to be discovered and run by pytest for PP1 evidence.
"""

import sys
import os
import numpy as np

# 1. Add the 'adaptive-pipeline' root directory to the system path
# This allows Python to recognize 'src' as a proper package
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

# 2. Import using the package name 'src'
from src.schema import EnrichedContextPayload
from src.state_assembler import assemble_state_vector


def test_schema_and_state_assembler_pipeline():
    """
    Pytest-compatible test function that validates:
    1. Complete mock payload parsing and state vector generation.
    2. Future-proofing (ignoring unknown extra fields).
    3. Partial payload handling (falling back to safe defaults).
    """
    print("\n=== TEST 1: Parsing Complete Mock Payload ===")
    sample_json = {
        "event_id": "evt-2026-001",
        "timestamp": "2026-08-18T10:00:00Z",
        "prediction_data": {
            "service_id": "payment-service",
            "failure_type": "MEMORY_LEAK",
            "failure_probability": 0.88,
            "estimated_time_to_failure_sec": 120
        },
        "graph_context": {
            "is_root_cause": True,
            "upstream_status": "HEALTHY",
            "downstream_impact_count": 3
        },
        "impact_assessment": {
            "blast_radius_score": 0.75,
            "severity_level": "HIGH"
        },
        "guardrail_status": {
            "cooldown_active": False,
            "time_since_last_action_sec": 600
        }
    }

    # Validate JSON -> Pydantic Model
    payload = EnrichedContextPayload(**sample_json)
    print(f"✅ Successfully parsed payload for service: {payload.prediction_data.service_id}")

    # Convert to State Vector
    state_vector = assemble_state_vector(payload)
    print(f"✅ Assembled State Vector S_t: {state_vector}")
    print(f"   Vector Shape: {state_vector.shape}, Type: {state_vector.dtype}")
    
    # Assert the shape is exactly 7 dimensions
    assert state_vector.shape == (7,), "State vector must be 7-dimensional"
    assert state_vector.dtype == np.float32, "State vector must be float32"

    print("\n=== TEST 2: Future Proofing - LiyanaArachchi Adds Unknown Extra Fields ===")
    dirty_json = sample_json.copy()
    dirty_json["unknown_new_field_from_liyanaarachchi"] = "some_data"
    dirty_json["prediction_data"]["extra_metric_xyz"] = 999

    payload_dirty = EnrichedContextPayload(**dirty_json)
    state_vector_dirty = assemble_state_vector(payload_dirty)
    print("✅ System successfully ignored unknown extra fields without crashing!")
    print(f"   Assembled Vector S_t: {state_vector_dirty}")
    
    # Assert it still produces a valid 7-dim vector
    assert state_vector_dirty.shape == (7,)

    print("\n=== TEST 3: Partial Payload - Missing Fields Fall Back to Defaults ===")
    empty_json = {}
    payload_empty = EnrichedContextPayload(**empty_json)
    state_vector_empty = assemble_state_vector(payload_empty)
    print("✅ Successfully handled completely empty payload using safe defaults!")
    print(f"   Default State Vector S_t: {state_vector_empty}")
    
    # Assert defaults work and shape is maintained
    assert state_vector_empty.shape == (7,)