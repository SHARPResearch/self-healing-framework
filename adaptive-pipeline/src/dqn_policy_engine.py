"""
DQN Policy Inference Engine.
Evaluates the 7-dimensional state vector and outputs the optimal recovery action.
"""

import torch
import torch.nn as nn
import numpy as np
from enum import Enum


class RecoveryAction(str, Enum):
    """Discrete action space for the RL agent."""
    DO_NOTHING = "DO_NOTHING"
    RESTART_SERVICE = "RESTART_SERVICE"
    SCALE_OUT = "SCALE_OUT"
    ROUTE_TRAFFIC = "ROUTE_TRAFFIC"


# Maps neural network output indices to Enum actions
ACTION_SPACE = [
    RecoveryAction.DO_NOTHING,
    RecoveryAction.RESTART_SERVICE,
    RecoveryAction.SCALE_OUT,
    RecoveryAction.ROUTE_TRAFFIC
]


class DQN(nn.Module):
    """
    Deep Q-Network Architecture.
    Maps a 7-dimensional state vector to Q-values for 4 possible actions.
    """
    def __init__(self, state_dim: int = 7, action_dim: int = 4):
        super(DQN, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(state_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, action_dim)
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Forward pass to calculate Q-values."""
        return self.network(state)


def get_optimal_action(state_vector: np.ndarray, model: DQN) -> tuple[RecoveryAction, float]:
    """
    Takes a 7-dim state vector, runs it through the DQN, and returns 
    the best action and its confidence score (Q-value).
    """
    # 1. Convert NumPy array to PyTorch Tensor and add batch dimension
    state_tensor = torch.FloatTensor(state_vector).unsqueeze(0)
    
    # 2. Set model to eval mode and disable gradient calculation for inference
    model.eval()
    with torch.no_grad():
        q_values = model(state_tensor)
        
    # 3. Find the action with the highest Q-value
    best_action_idx = torch.argmax(q_values).item()
    best_q_value = q_values[0, best_action_idx].item()
    
    # 4. Map index to Enum action
    best_action = ACTION_SPACE[best_action_idx]
    
    return best_action, best_q_value