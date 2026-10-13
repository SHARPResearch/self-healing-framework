"""
End-to-End Pipeline Demonstration Script.
Simulates the full flow: Mock Data -> Schema Validation -> State Assembly -> DQN Inference.
This script is designed to be run live during the PP1 presentation.
"""

import sys
import os
import json

# Ensure the adaptive-pipeline root directory is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.mock_prometheus_data import MockPrometheusGenerator
from src.schema import EnrichedContextPayload
from src.state_assembler import assemble_state_vector
from src.dqn_policy_engine import DQN, get_optimal_action


def run_demo():
    print("=" * 75)
    print(" 🚀 ADAPTIVE LEARNING DECISION ENGINE - PP1 LIVE DEMO 🚀")
    print("=" * 75)
    
    # Step 1: Generate Mock Input
    print("\n[STEP 1] Generating Mock Telemetry from Upstream Engine...")
    json_payload = MockPrometheusGenerator.get_json_string("memory_leak")
    print("✅ Received Payload (truncated for display):")
    print(json_payload[:350] + "...\n")
    
    # Step 2: Schema Validation
    print("[STEP 2] Validating Payload via Data Contract (schema.py)...")
    payload_dict = json.loads(json_payload)
    payload = EnrichedContextPayload(**payload_dict)
    print(f"✅ Validation Successful! Target Service: {payload.prediction_data.service_id}")
    print(f"   Failure Type: {payload.prediction_data.failure_type.value}")
    print(f"   Probability: {payload.prediction_data.failure_probability}\n")
    
    # Step 3: State Assembly
    print("[STEP 3] Assembling 7-Dimensional State Vector (state_assembler.py)...")
    state_vector = assemble_state_vector(payload)
    print(f"✅ State Vector S_t Generated:")
    print(f"   {state_vector}")
    print(f"   Shape: {state_vector.shape}, Dtype: {state_vector.dtype}\n")
    
    # Step 4: DQN Inference
    print("[STEP 4] Evaluating State via Deep Q-Network (dqn_policy_engine.py)...")
    # Initialize a fresh DQN for demonstration purposes
    model = DQN(state_dim=7, action_dim=4)
    action, q_value = get_optimal_action(state_vector, model)
    
    print(f"✅ Inference Complete!")
    print(f"   Recommended Action: {action.value}")
    print(f"   Confidence (Q-Value): {q_value:.4f}\n")
    
    print("=" * 75)
    print(" 🎉 END-TO-END PIPELINE EXECUTED SUCCESSFULLY 🎉")
    print("=" * 75)


if __name__ == "__main__":
    run_demo()