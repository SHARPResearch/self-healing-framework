"""
test_reward_calculator.py
Tests to prove our Judge (Reward Calculator) correctly scores actions.
"""
import pytest
from app.reward_calculator import RewardCalculator
from app.dueling_dqn import RecoveryAction

def test_reward_for_successful_recovery():
    """If the anomaly score drops, the reward should be positive."""
    calculator = RewardCalculator()
    # Score drops from 0.8 to 0.2 (Delta = 0.6)
    reward = calculator.calculate_reward(0.8, 0.2, RecoveryAction.RESTART_POD)
    assert reward > 0, "Successful recovery should yield a positive reward"

def test_reward_for_regression():
    """If the anomaly score increases, the heavy regression penalty should apply."""
    calculator = RewardCalculator()
    # Score goes UP from 0.5 to 0.7 (Regression!)
    reward = calculator.calculate_reward(0.5, 0.7, RecoveryAction.SCALE_UP)
    # The penalty is -5.0, so the total reward must be heavily negative
    assert reward < -4.0, "Regression should trigger a massive negative reward (delta=5.0)"

def test_reward_for_no_action():
    """NO_ACTION has zero cost, so reward is purely based on anomaly delta."""
    calculator = RewardCalculator()
    # Score stays exactly the same
    reward = calculator.calculate_reward(0.5, 0.5, RecoveryAction.NO_ACTION)
    assert reward == 0.0, "No change and no action should result in exactly 0.0 reward"

def test_reward_conflict_penalty():
    """If there is a conflict, the gamma penalty should be applied."""
    calculator = RewardCalculator()
    reward_no_conflict = calculator.calculate_reward(0.8, 0.2, RecoveryAction.RESTART_POD, is_conflict=False)
    reward_with_conflict = calculator.calculate_reward(0.8, 0.2, RecoveryAction.RESTART_POD, is_conflict=True)
    
    # The conflict reward should be exactly 0.5 (GAMMA) lower than the non-conflict reward
    assert reward_no_conflict - reward_with_conflict == pytest.approx(0.5, abs=1e-5)