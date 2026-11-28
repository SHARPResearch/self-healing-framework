"""
reward_calculator.py
The "Judge" for Component 3.
Calculates the reward signal based on the exact formula from Component 3 §4.1.
"""
import numpy as np
from .dueling_dqn import RecoveryAction

# Action Costs (Intrinsic risk/effort of each action)
# Defined in Component 3 §4.1: β · cost(a_t)
ACTION_COSTS = {
    RecoveryAction.NO_ACTION: 0.0,
    RecoveryAction.FLUSH_CACHE: 0.1,
    RecoveryAction.CLOSE_CIRCUIT: 0.1,
    RecoveryAction.SCALE_UP: 0.3,
    RecoveryAction.SCALE_CONSUMERS: 0.3,
    RecoveryAction.INCREASE_DB_POOL: 0.4,
    RecoveryAction.RESTART_POD: 0.5,
    RecoveryAction.ROLLBACK: 0.6,
    RecoveryAction.SCALE_DOWN: 0.2,
    RecoveryAction.OPEN_CIRCUIT: 0.4,
    RecoveryAction.REROUTE_TRAFFIC: 0.5
}

# Reward Function Weights (From Component 3 §4.1)
ALPHA = 1.0   # Benefit: anomaly reduction
BETA = 0.3    # Cost: action intrinsic risk
GAMMA = 0.5   # Penalty: conflicting actions
DELTA = 5.0   # Penalty: harmful action (regression)


class RewardCalculator:
    def calculate_reward(
        self, 
        anomaly_score_before: float, 
        anomaly_score_after: float, 
        action: RecoveryAction, 
        is_conflict: bool = False
    ) -> float:
        """
        Calculates the reward R_t based on the multi-objective formula:
        R_t = α·Δ(anomaly_score) - β·cost(a_t) - γ·conflict - δ·1[regression]
        """
        # 1. Calculate Anomaly Reduction (Δ)
        # If score goes from 0.8 to 0.2, delta is 0.6 (Positive benefit)
        anomaly_delta = anomaly_score_before - anomaly_score_after
        
        # 2. Get Action Cost
        action_cost = ACTION_COSTS.get(action, 0.5)
        
        # 3. Detect Regression (Did the agent make things worse?)
        # If anomaly_score_after > anomaly_score_before, it's a regression
        is_regression = anomaly_score_after > anomaly_score_before
        regression_penalty = DELTA if is_regression else 0.0
        
        # 4. Conflict Penalty
        conflict_penalty = GAMMA if is_conflict else 0.0
        
        # 5. Final Calculation
        reward = (ALPHA * anomaly_delta) - (BETA * action_cost) - conflict_penalty - regression_penalty
        
        return float(reward)

    def calculate_counterfactual_reward(
        self, 
        simulated_anomaly_drop: float, 
        action: RecoveryAction, 
        simulated_is_regression: bool = False
    ) -> float:
        """
        Calculates the hypothetical reward for Shadow Mode actions.
        Used when the RL action was NOT executed, but we have simulation data.
        Formula: R_cf = α·Δ_simulated - β·cost(a) - δ·1[regression_simulated]
        """
        action_cost = ACTION_COSTS.get(action, 0.5)
        regression_penalty = DELTA if simulated_is_regression else 0.0
        
        reward = (ALPHA * simulated_anomaly_drop) - (BETA * action_cost) - regression_penalty
        return float(reward)

    def get_reward_breakdown(
        self, 
        anomaly_score_before: float, 
        anomaly_score_after: float, 
        action: RecoveryAction, 
        is_conflict: bool = False
    ) -> dict:
        """
        Returns a detailed JSON-serializable breakdown of the reward calculation.
        Used for LLM Copilot explainability and dashboard telemetry.
        """
        anomaly_delta = anomaly_score_before - anomaly_score_after
        action_cost = ACTION_COSTS.get(action, 0.5)
        is_regression = anomaly_score_after > anomaly_score_before
        regression_penalty = DELTA if is_regression else 0.0
        conflict_penalty = GAMMA if is_conflict else 0.0
        
        final_reward = (ALPHA * anomaly_delta) - (BETA * action_cost) - conflict_penalty - regression_penalty
        
        return {
            "action": action.value,
            "anomaly_delta": float(anomaly_delta),
            "action_cost": float(action_cost),
            "conflict_penalty": float(conflict_penalty),
            "regression_penalty": float(regression_penalty),
            "final_reward": float(final_reward)
        }

    def fetch_anomaly_scores_from_db(self, anomaly_id: str) -> tuple:
        """
        Fetches the 'before' and 'after' anomaly scores from the database.
        (Simplified for Phase 5; will be fully integrated with telemetry in Phase 6)
        """
        from .db_reader import fetch_anomaly_events
        events = fetch_anomaly_events(limit=10)
        
        # For now, we simulate the before/after based on the event's current score
        # In Phase 6, we will query the exact time-series snapshots
        event = next((e for e in events if e['id'] == anomaly_id), None)
        if event:
            score_before = float(event.get('anomaly_score', 0.5))
            score_after = score_before * 0.5  # Simulating a 50% recovery
            return score_before, score_after
            
        return 0.8, 0.2  # Fallback defaults
    