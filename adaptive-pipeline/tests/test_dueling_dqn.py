"""
test_dueling_dqn.py
Tests to prove our Super (Dueling DQN) brain works correctly.
"""
import torch
from app.dueling_dqn import DuelingDQN, NUM_ACTIONS

def test_dueling_dqn_output_shape():
    """The network must output exactly 11 Q-values (one for each action)."""
    # Initialize the brain for a 55-dim state
    model = DuelingDQN(state_dim=55, action_dim=NUM_ACTIONS)
    model.eval() # Set to evaluation mode
    
    # Create a fake 55-dim state vector (batch size of 1)
    fake_state = torch.randn(1, 55)
    
    with torch.no_grad():
        q_values = model(fake_state)
        
    # Prove the output shape is [1, 11]
    assert q_values.shape == (1, 11), f"Expected shape (1, 11), got {q_values.shape}"

def test_dueling_dqn_batch_processing():
    """The network must handle multiple states at once (batching)."""
    model = DuelingDQN(state_dim=55, action_dim=NUM_ACTIONS)
    model.eval()
    
    # Create a fake batch of 8 different state vectors
    fake_batch = torch.randn(8, 55)
    
    with torch.no_grad():
        q_values = model(fake_batch)
        
    # Prove the output shape is [8, 11]
    assert q_values.shape == (8, 11), f"Expected shape (8, 11), got {q_values.shape}"