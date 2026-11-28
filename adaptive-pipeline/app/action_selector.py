"""
action_selector.py
The "Exploration vs Exploitation" module for Component 3.
Decides whether the  should try a random action or use its trained Brain.
"""
import random
import numpy as np
import torch
from .dueling_dqn import DuelingDQN, ACTION_SPACE, RecoveryAction

class ActionSelector:
    def __init__(self, policy_net: DuelingDQN, epsilon_start: float = 1.0, epsilon_end: float = 0.05, epsilon_decay: float = 0.995):
        self.policy_net = policy_net
        self.epsilon = epsilon_start
        self.epsilon_min = epsilon_end
        self.epsilon_decay = epsilon_decay

    def select_action(self, state: np.ndarray) -> RecoveryAction:
        """
        Epsilon-Greedy Strategy.
        With probability epsilon, pick a random action (Explore).
        Otherwise, pick the best action from the Brain (Exploit).
        """
        if random.random() < self.epsilon:
            # Explore: Pick a random action
            return random.choice(ACTION_SPACE)
        else:
            # Exploit: Use the Brain
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
                q_values = self.policy_net(state_tensor)
                best_action_idx = q_values.argmax(dim=1).item()
                return ACTION_SPACE[best_action_idx]

    def decay_epsilon(self):
        """Slowly reduce exploration as the Puppy gets smarter."""
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay