"""
test_replay_buffer.py
Tests to prove our Memory Bank can store and sample experiences correctly.
"""
import numpy as np
from app.replay_buffer import ReplayBuffer

def test_replay_buffer_push_and_sample():
    """The buffer should store experiences and return the correct batch shapes."""
    buffer = ReplayBuffer(capacity=100)
    
    # Push 10 fake experiences
    for i in range(10):
        state = np.random.rand(55)
        buffer.push(state, action=1, reward=1.0, next_state=np.random.rand(55), done=False)
        
    assert len(buffer) == 10, "Buffer should have 10 items"
    
    # Sample a batch of 4
    batch = buffer.sample(batch_size=4)
    states, actions, rewards, next_states, dones = batch
    
    assert states.shape == (4, 55), f"Expected states shape (4, 55), got {states.shape}"
    assert len(actions) == 4

def test_replay_buffer_capacity_limit():
    """The buffer should not exceed its maximum capacity."""
    buffer = ReplayBuffer(capacity=5)
    
    # Push 10 experiences into a capacity-5 buffer
    for i in range(10):
        buffer.push(np.zeros(55), 0, 0.0, np.zeros(55), False)
        
    assert len(buffer) == 5, "Buffer should be capped at 5 items"