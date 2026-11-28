"""
shadow_observer.py
The "Time Machine" for Component 3.
Reads LiyanaArachchi's shadow_records from the DB and calculates counterfactual rewards.
"""
import logging
from .db_reader import fetch_shadow_records
from .reward_calculator import RewardCalculator
from .dueling_dqn import RecoveryAction

log = logging.getLogger(__name__)

class ShadowObserver:
    def __init__(self):
        self.calculator = RewardCalculator()

    def process_shadow_records(self, limit: int = 50) -> list:
        """
        Fetches recent shadow records and calculates what the RL agent 
        WOULD have scored if its action had been executed.
        """
        records = fetch_shadow_records(limit=limit)
        results = []
        
        for record in records:
            # 1. Extract the simulated data from Liyana's DB
            simulated_outcome = record.get('simulated_outcome', {})
            simulated_drop = simulated_outcome.get('expected_anomaly_drop', 0.0)
            
            # 2. Check if the simulation says it would have been a disaster
            is_regression = simulated_drop < 0.0 
            
            # 3. Map the DB action string to our RecoveryAction Enum
            action_str = record.get('candidate_action', 'NO_ACTION').upper()
            try:
                action = RecoveryAction[action_str]
            except KeyError:
                action = RecoveryAction.NO_ACTION
                
            # 4. Calculate the Counterfactual Reward
            reward = self.calculator.calculate_counterfactual_reward(
                simulated_anomaly_drop=simulated_drop,
                action=action,
                simulated_is_regression=is_regression
            )
            
            results.append({
                "shadow_id": record.get('id'),
                "service_id": record.get('service_id'),
                "action": action.value,
                "simulated_drop": simulated_drop,
                "counterfactual_reward": reward
            })
            
        log.info(f"Processed {len(results)} shadow records for counterfactual learning.")
        return results