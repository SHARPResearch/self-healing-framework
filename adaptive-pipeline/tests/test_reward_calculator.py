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

def test_counterfactual_reward_for_shadow_mode():
    """The calculator should compute hypothetical rewards for unexecuted Shadow Mode actions."""
    calculator = RewardCalculator()
    
    # Simulate a scenario where the action WOULD have dropped the anomaly by 0.5
    reward = calculator.calculate_counterfactual_reward(
        simulated_anomaly_drop=0.5, 
        action=RecoveryAction.RESTART_POD, 
        simulated_is_regression=False
    )
    
    # 0.5 (drop) - 0.3 * 0.5 (cost of RESTART_POD) = 0.5 - 0.15 = 0.35
    assert reward == pytest.approx(0.35, abs=1e-5), "Counterfactual reward math is incorrect"

def test_counterfactual_reward_for_simulated_regression():
    """If the simulation shows the action would have made things worse, apply heavy penalty."""
    calculator = RewardCalculator()
    
    reward = calculator.calculate_counterfactual_reward(
        simulated_anomaly_drop=-0.2, # Negative drop means it got worse
        action=RecoveryAction.SCALE_UP, 
        simulated_is_regression=True
    )
    
    # Should be heavily negative due to the 5.0 delta penalty
    assert reward < -4.0, "Simulated regression should trigger massive counterfactual penalty"

# def test_reward_breakdown_returns_valid_json_structure():
#     """The breakdown method should return a dictionary with all required keys for the LLM Copilot."""
#     calculator = RewardCalculator()
#     breakdown = calculator.get_reward_breakdown(0.8, 0.2, RecoveryAction.RESTART_POD)
    
#     required_keys = ["action", "anomaly_delta", "action_cost", "conflict_penalty", "regression_penalty", "final_reward"]
#     for key in required_keys:
#         assert key in breakdown, f"Missing key {key} in reward breakdown"
        
#     assert breakdown["action"] == "RESTART_POD"
#     assert breakdown["final_reward"] > 0