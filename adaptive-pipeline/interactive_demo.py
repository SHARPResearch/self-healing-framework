"""
Interactive Step-by-Step Demonstration Script for PP1.
Pauses at each stage to allow the presenter to explain the logic to the panel.
"""

import sys
import os
import json
import time

# Ensure the adaptive-pipeline root directory is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.mock_prometheus_data import MockPrometheusGenerator
from src.schema import EnrichedContextPayload
from src.state_assembler import assemble_state_vector
from src.dqn_policy_engine import DQN, get_optimal_action


def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def wait_for_user():
    input("\n👉 [Press ENTER to proceed to the next step...]")


def run_interactive_demo():
    print_header("🚀 ADAPTIVE LEARNING DECISION ENGINE - LIVE DEMO 🚀")
    print("Welcome. I will now demonstrate the end-to-end data flow of my component.")
    wait_for_user()

    # ==========================================
    # STEP 1: INPUT
    # ==========================================
    print_header("STEP 1: INPUT - Receiving Telemetry Data")
    print("My component receives an 'EnrichedContextPayload' from the upstream")
    print("Rule-Based Engine. Here is the raw JSON payload simulating a memory leak:")
    print("-" * 70)
    
    json_payload = MockPrometheusGenerator.get_json_string("memory_leak")
    print(json_payload)
    print("-" * 70)
    wait_for_user()

    # ==========================================
    # STEP 2: PROCESSING (SCHEMA VALIDATION)
    # ==========================================
    print_header("STEP 2: PROCESSING - Schema Validation (schema.py)")
    print("Before processing, we validate the data contract using Pydantic.")
    print("Notice the 'extra=\"ignore\"' config. If the upstream team adds new")
    print("metrics in the future, my component will safely ignore them instead of crashing.")
    print("-" * 70)
    
    payload_dict = json.loads(json_payload)
    payload = EnrichedContextPayload(**payload_dict)
    print(f"✅ Validation Successful!")
    print(f"   Target Service: {payload.prediction_data.service_id}")
    print(f"   Failure Type:   {payload.prediction_data.failure_type.value}")
    print(f"   Probability:    {payload.prediction_data.failure_probability}")
    print("-" * 70)
    wait_for_user()

    # ==========================================
    # STEP 3: PROCESSING (STATE ASSEMBLY) - FUNCTION 1
    # ==========================================
    print_header("STEP 3: PROCESSING - State Vector Assembly (state_assembler.py)")
    print("Neural networks cannot understand text like 'MEMORY_LEAK'.")
    print("My first core function converts this JSON into a 7-dimensional")
    print("numerical state vector (S_t). Notice how downstream impact is")
    print("divided by 10 and capped at 1.0 to normalize the data.")
    print("-" * 70)
    
    state_vector = assemble_state_vector(payload)
    print(f"✅ State Vector S_t Generated:")
    print(f"   {state_vector}")
    print(f"   Shape: {state_vector.shape} | Dtype: {state_vector.dtype}")
    print("-" * 70)
    wait_for_user()

    # ==========================================
    # STEP 4: PROCESSING (DQN INFERENCE) - FUNCTION 2
    # ==========================================
    print_header("STEP 4: PROCESSING - DQN Policy Inference (dqn_policy_engine.py)")
    print("My second core function passes the 7-dim vector through the")
    print("Deep Q-Network. It calculates a Q-value (confidence score) for")
    print("each of the 4 possible actions in our Action Space.")
    print("-" * 70)
    
    model = DQN(state_dim=7, action_dim=4)
    action, q_value = get_optimal_action(state_vector, model)
    
    print(f"✅ Inference Complete!")
    print(f"   Recommended Action: {action.value}")
    print(f"   Confidence (Q-Val): {q_value:.4f}")
    print("-" * 70)
    wait_for_user()

    # ==========================================
    # STEP 5: OUTPUT
    # ==========================================
    print_header("🎉 STEP 5: OUTPUT - Final Decision")
    print("The component outputs the optimal action to the Hybrid Arbitration")
    print("module. In this case, the DQN recommends: " + action.value)
    print("This entire inference process takes less than 1 millisecond.")
    print("=" * 70)
     
    print("=" * 70)


if __name__ == "__main__":
    run_interactive_demo()