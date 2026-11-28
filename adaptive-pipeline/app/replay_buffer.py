"""
replay_buffer.py
The "Memory Bank" for Component 3.
Stores the Super Brain's past experiences so it can learn from them later.
"""
import random
import numpy as np
from collections import deque
from typing import Tuple, List

class ReplayBuffer:
    def __init__(self, capacity: int = 10000):
        # A deque automatically removes the oldest memory when it gets too full
        self.buffer = deque(maxlen=capacity)

    def push(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool):
        """Write a new experience in the diary."""
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> Tuple[np.ndarray, ...]:
        """Randomly flip through the diary to learn from past experiences."""
        batch = random.sample(self.buffer, batch_size)
        
        # Unpack the batch into separate arrays for the neural network
        states, actions, rewards, next_states, dones = zip(*batch)
        
        return (
            np.array(states),
            np.array(actions),
            np.array(rewards),
            np.array(next_states),
            np.array(dones)
        )

    def __len__(self) -> int:
        return len(self.buffer)