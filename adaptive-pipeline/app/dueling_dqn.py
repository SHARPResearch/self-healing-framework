"""
dueling_dqn.py
The "Super Brain" for Component 3.
Uses Dueling DQN architecture to separate state value from action advantage.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from enum import Enum
from typing import List

# The 11 discrete actions defined in the Component 3 research proposal
class RecoveryAction(str, Enum):
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
    RESTART_POD = "RESTART_POD"
    ROLLBACK = "ROLLBACK"
    OPEN_CIRCUIT = "OPEN_CIRCUIT"
    CLOSE_CIRCUIT = "CLOSE_CIRCUIT"
    FLUSH_CACHE = "FLUSH_CACHE"
    INCREASE_DB_POOL = "INCREASE_DB_POOL"
    SCALE_CONSUMERS = "SCALE_CONSUMERS"
    REROUTE_TRAFFIC = "REROUTE_TRAFFIC"
    NO_ACTION = "NO_ACTION"

ACTION_SPACE: List[RecoveryAction] = [action for action in RecoveryAction]
NUM_ACTIONS = len(ACTION_SPACE) # 11

class DuelingDQN(nn.Module):
    """
    The Dueling DQN Architecture.
    Splits the network into a Value stream and an Advantage stream.
    """
    def __init__(self, state_dim: int = 55, action_dim: int = NUM_ACTIONS):
        super(DuelingDQN, self).__init__()
        
        # Shared feature extraction layers (The Puppy's eyes)
        self.feature_layer = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU()
        )
        
        # Value Stream (How good is the state overall?)
        self.value_stream = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1)  # Outputs a single scalar V(s)
        )
        
        # Advantage Stream (How much better is this action than average?)
        self.advantage_stream = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, action_dim)  # Outputs A(s,a) for all 11 actions
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass combining Value and Advantage streams.
        Formula: Q(s,a) = V(s) + (A(s,a) - mean(A(s,a')))
        """
        # 1. Extract shared features
        features = self.feature_layer(x)
        
        # 2. Calculate Value and Advantage
        value = self.value_stream(features)
        advantage = self.advantage_stream(features)
        
        # 3. Combine them using the Dueling DQN aggregation formula
        # We subtract the mean advantage to ensure identifiability
        q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))
        
        return q_values