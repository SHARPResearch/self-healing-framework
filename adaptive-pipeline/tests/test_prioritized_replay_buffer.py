"""
test_prioritized_replay_buffer.py
Tests to prove our Smart Memory Bank prioritizes surprising experiences.
"""
import numpy as np
from app.prioritized_replay_buffer import PrioritizedReplayBuffer

def test_per_favors_high_priority_items():
    """The buffer should sample high-priority items significantly more often."""
    buffer = PrioritizedReplayBuffer(capacity=100)
    
    # Push 10 experiences
    for i in range(10):
        buffer.push(np.zeros(55), i, 0.0, np.zeros(55), False)
        
    # Make experience #0 extremely important (high priority)
    buffer.priorities[0] = 1000.0
    # Keep others low
    buffer.priorities[1:] = 1.0
    
    # Sample 1000 times
    sample_count = np.zeros(10)
    for _ in range(1000):
        _, _, _, _, _, _, indices = buffer.sample(batch_size=1)
        sample_count[indices[0]] += 1
        
    # Experience #0 should be sampled way more than the others
    assert sample_count[0] > 500, f"High priority item should be sampled >500 times, got {sample_count[0]}"
    assert sample_count[0] > sample_count[1] * 10, "High priority item should dominate low priority items"

def test_per_updates_priorities():
    """The buffer should allow updating priorities after learning."""
    buffer = PrioritizedReplayBuffer(capacity=10)
    buffer.push(np.zeros(55), 0, 0.0, np.zeros(55), False)
    
    # Update the priority of the first item based on a large TD error
    buffer.update_priorities(indices=[0], td_errors=[5.0])
    
    assert buffer.priorities[0] == 5.0 + 1e-5, "Priority should be updated to TD error + epsilon"