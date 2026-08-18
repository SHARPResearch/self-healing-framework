"""
test_aug13.py
Verifies schema parsing, default handling, and state vector transformation.
"""

from src.schema import EnrichedContextPayload
from src.state_assembler import assemble_state_vector

def run_tests():
    print("=== TEST 1: Parsing Complete Mock Payload ===")
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

    print("\n=== TEST 2: Future Proofing - LiyanaArachchi Adds Unknown Extra Fields ===")
    dirty_json = sample_json.copy()
    dirty_json["unknown_new_field_from_liyanaarachchi"] = "some_data"
    dirty_json["prediction_data"]["extra_metric_xyz"] = 999

    payload_dirty = EnrichedContextPayload(**dirty_json)
    state_vector_dirty = assemble_state_vector(payload_dirty)
    print("✅ System successfully ignored unknown extra fields without crashing!")
    print(f"   Assembled Vector S_t: {state_vector_dirty}")

    print("\n=== TEST 3: Partial Payload - Missing Fields Fall Back to Defaults ===")
    empty_json = {}
    payload_empty = EnrichedContextPayload(**empty_json)
    state_vector_empty = assemble_state_vector(payload_empty)
    print("✅ Successfully handled completely empty payload using safe defaults!")
    print(f"   Default State Vector S_t: {state_vector_empty}")

if __name__ == "__main__":
    run_tests()