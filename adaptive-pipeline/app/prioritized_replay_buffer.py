"""
prioritized_replay_buffer.py
The "Smart Memory Bank" for Component 3.
Uses Prioritized Experience Replay (PER) to learn from surprising experiences faster.
"""
import numpy as np
import torch
from typing import Tuple

class PrioritizedReplayBuffer:
    def __init__(self, capacity: int = 10000, alpha: float = 0.6):
        self.capacity = capacity
        self.alpha = alpha  # 0 = random sampling, 1 = fully prioritized
        self.buffer = []
        self.priorities = np.array([], dtype=np.float32)

    def push(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool):
        """Write a new experience, giving it the maximum priority initially."""
        max_p = self.priorities.max() if len(self.priorities) > 0 else 1.0
        
        self.buffer.append((state, action, reward, next_state, done))
        self.priorities = np.append(self.priorities, max_p)

        # If we exceed capacity, drop the oldest memory
        if len(self.buffer) > self.capacity:
            self.buffer.pop(0)
            self.priorities = np.delete(self.priorities, 0)

    def sample(self, batch_size: int, beta: float = 0.4) -> Tuple:
        """Sample experiences, but favor the ones with high priorities."""
        if len(self.buffer) == 0:
            return None

        # Calculate sampling probabilities based on priorities
        probs = self.priorities ** self.alpha
        probs /= probs.sum()

        # Sample indices based on these probabilities
        indices = np.random.choice(len(self.buffer), batch_size, p=probs)

        # Calculate Importance Sampling (IS) weights to correct bias
        weights = (len(self.buffer) * probs[indices]) ** (-beta)
        weights /= weights.max()  # Normalize weights

        batch = [self.buffer[idx] for idx in indices]
        states, actions, rewards, next_states, dones = zip(*batch)

        return (
            np.array(states), np.array(actions), np.array(rewards),
            np.array(next_states), np.array(dones),
            torch.FloatTensor(weights),
            indices
        )

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray):
        """After learning, update the priority of the experiences based on how surprised the agent was."""
        for idx, error in zip(indices, td_errors):
            self.priorities[idx] = abs(error) + 1e-5  # Add epsilon to avoid zero priority