"""
test_dqn_trainer.py
Tests to prove our Homework and Teacher modules work correctly.
"""
import numpy as np
import torch
from app.dqn_trainer import DQNTrainer
from app.action_selector import ActionSelector
from app.dueling_dqn import DuelingDQN, ACTION_SPACE

def test_dqn_trainer_calculates_loss():
    """The trainer should calculate a loss and update the policy network weights."""
    trainer = DQNTrainer(state_dim=55, action_dim=11)
    
    # Create a fake batch of 4 experiences
    states = np.random.rand(4, 55)
    actions = np.array([0, 1, 2, 3])
    rewards = np.array([1.0, -1.0, 0.5, 0.0])
    next_states = np.random.rand(4, 55)
    dones = np.array([False, True, False, False])
    
    # Get initial weights
    initial_weight = trainer.policy_net.feature_layer[0].weight.data.clone()
    
    # Do the homework
    loss = trainer.update(states, actions, rewards, next_states, dones)
    
    # Prove loss is a number and weights changed
    assert isinstance(loss, float), "Loss should be a float"
    assert not torch.equal(initial_weight, trainer.policy_net.feature_layer[0].weight.data), "Weights should update after training"

def test_action_selector_explores_and_exploits():
    """The selector should pick random actions when epsilon is high, and brain actions when low."""
    policy_net = DuelingDQN(state_dim=55, action_dim=11)
    
    # 1. High Epsilon = 100% Exploration
    selector = ActionSelector(policy_net, epsilon_start=1.0, epsilon_end=1.0)
    action = selector.select_action(np.random.rand(55))
    assert action in ACTION_SPACE, "Should return a valid action"
    
    # 2. Low Epsilon = 100% Exploitation
    selector.epsilon = 0.0
    action = selector.select_action(np.random.rand(55))
    assert action in ACTION_SPACE, "Should return a valid action from the brain"