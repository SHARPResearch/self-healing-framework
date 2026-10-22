"""
Tests for the DQN Policy Inference Engine.
Validates network architecture, forward pass, and action mapping.
"""

import sys
import os
import numpy as np
import torch

# Add root directory to path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from src.dqn_policy_engine import DQN, get_optimal_action, RecoveryAction, ACTION_SPACE


def test_dqn_initialization_and_forward_pass():
    """Test that the DQN initializes and outputs the correct shape."""
    model = DQN(state_dim=7, action_dim=4)
    
    # Create a mock 7-dim state vector
    mock_state = np.array([0.88, 1.0, 1.0, 0.0, 0.3, 0.75, 0.0], dtype=np.float32)
    state_tensor = torch.FloatTensor(mock_state).unsqueeze(0)
    
    # Run forward pass
    q_values = model(state_tensor)
    
    # Assert output shape is [batch_size, num_actions] -> [1, 4]
    assert q_values.shape == (1, 4), f"Expected shape (1, 4), got {q_values.shape}"


def test_get_optimal_action_inference():
    """Test the full inference pipeline from state vector to action."""
    model = DQN(state_dim=7, action_dim=4)
    
    # Mock state vector (e.g., High probability memory leak)
    mock_state = np.array([0.88, 1.0, 1.0, 0.0, 0.3, 0.75, 0.0], dtype=np.float32)
    
    action, q_value = get_optimal_action(mock_state, model)
    
    # Assert it returns a valid RecoveryAction enum
    assert isinstance(action, RecoveryAction), "Output must be a RecoveryAction Enum"
    assert action in ACTION_SPACE, "Action must be in the defined action space"
    
    # Assert Q-value is a float
    assert isinstance(q_value, float), "Q-value must be a float"
    
    print(f"\n✅ Inference successful! Action: {action.value}, Q-Value: {q_value:.4f}")