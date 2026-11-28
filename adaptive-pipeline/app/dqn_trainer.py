"""
dqn_trainer.py
The "Homework & Teacher" module for Component 3.
Calculates TD Error to update the main brain, and manages the frozen Target Brain.
"""
import torch
import torch.nn as nn
import torch.optim as optim
from .dueling_dqn import DuelingDQN
from .config import settings

class DQNTrainer:
    def __init__(self, state_dim: int = 55, action_dim: int = 11):
        # 1. The   Main Brain (Learns and changes)
        self.policy_net = DuelingDQN(state_dim, action_dim)
        
        # 2. The Teacher Brain (Frozen, used for stable targets)
        self.target_net = DuelingDQN(state_dim, action_dim)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval() # Teacher never learns directly
        
        # 3. The Pencil (Optimizer) - Learning rate from Component 3 §11
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=settings.dqn_learning_rate)
        
        # 4. The Homework Grader (Loss Function)
        self.loss_fn = nn.MSELoss()
        
        self.steps_done = 0

        

    def update(self, states, actions, rewards, next_states, dones):
        """
        Calculates the TD Error and updates the Main Brain.
        Formula: L(θ) = E[(r + γ * max Q_target(s', a') - Q_policy(s, a))^2]
        """
        batch_size = states.shape[0]
        
        # Convert numpy arrays to PyTorch tensors
        states = torch.FloatTensor(states)
        actions = torch.LongTensor(actions).unsqueeze(1)
        rewards = torch.FloatTensor(rewards).unsqueeze(1)
        next_states = torch.FloatTensor(next_states)
        dones = torch.FloatTensor(dones).unsqueeze(1)

        # 1. Get current Q-values from the Main Brain for the actions taken
        # Q_policy(s, a)
        current_q_values = self.policy_net(states).gather(1, actions)

        # 2. Get target Q-values from the Teacher Brain
        # max Q_target(s', a')
        with torch.no_grad(): # Teacher brain doesn't need gradients
            next_q_values = self.target_net(next_states).max(1)[0].unsqueeze(1)
            
        # Calculate expected Q-values: r + γ * max Q_target(s', a')
        # If the episode is done (dones=1), the future reward is 0
        expected_q_values = rewards + (settings.dqn_gamma * next_q_values * (1 - dones))

        # 3. Calculate TD Error (MSE Loss)
        loss = self.loss_fn(current_q_values, expected_q_values)

        # 4. Backpropagation (Do the homework!)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        self.steps_done += 1
        
        # 5. Sync Teacher Brain every N steps (Component 3 §11: DQN_TARGET_UPDATE_FREQ=100)
        if self.steps_done % 100 == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())
            
        return loss.item()