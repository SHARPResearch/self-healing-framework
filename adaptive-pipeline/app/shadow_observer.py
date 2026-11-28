"""
shadow_observer.py
The "Time Machine" for Component 3.
Reads LiyanaArachchi's shadow_records from the DB and calculates counterfactual rewards.
Automatically falls back to the ShadowSimulator and VerdictMapper if DB data is incomplete.
"""
import logging
from .db_reader import fetch_shadow_records
from .reward_calculator import RewardCalculator
from .dueling_dqn import RecoveryAction
from .shadow_simulator import ShadowSimulator
from .verdict_mapper import VerdictMapper

log = logging.getLogger(__name__)

class ShadowObserver:
    def __init__(self):
        self.calculator = RewardCalculator()
        self.simulator = ShadowSimulator()
        self.mapper = VerdictMapper()

    def process_shadow_records(self, limit: int = 50) -> list:
        """
        Fetches recent shadow records and calculates what the RL agent 
        WOULD have scored if its action had been executed.
        """
        records = fetch_shadow_records(limit=limit)
        results = []
        
        for record in records:
            simulated_outcome = record.get('simulated_outcome', {})
            simulated_drop = simulated_outcome.get('expected_anomaly_drop')
            verdict_str = record.get('verdict')
            
            # FALLBACK LOGIC: If DB is missing data, use the Imagination Engine!
            if simulated_drop is None:
                log.info(f"DB missing simulated_drop for {record.get('id')}. Using ShadowSimulator fallback.")
                action_str = record.get('candidate_action', 'NO_ACTION').upper()
                try:
                    action = RecoveryAction[action_str]
                except KeyError:
                    action = RecoveryAction.NO_ACTION
                simulated_drop = self.simulator.estimate_anomaly_drop(action)
                
            if verdict_str is None:
                log.info(f"DB missing verdict for {record.get('id')}. Using VerdictMapper fallback.")
                verdict_multiplier = 1.0 # Default to neutral if unknown
            else:
                verdict_multiplier = self.mapper.get_multiplier(verdict_str)

            # Map the DB action string to our RecoveryAction Enum
            action_str = record.get('candidate_action', 'NO_ACTION').upper()
            try:
                action = RecoveryAction[action_str]
            except KeyError:
                action = RecoveryAction.NO_ACTION
                
            is_regression = simulated_drop < 0.0 
            
            # Calculate the Counterfactual Reward
            reward = self.calculator.calculate_counterfactual_reward(
                simulated_anomaly_drop=simulated_drop,
                action=action,
                simulated_is_regression=is_regression
            )
            
            # Apply the verdict multiplier from the Translator
            final_reward = reward * verdict_multiplier
            
            results.append({
                "shadow_id": record.get('id'),
                "service_id": record.get('service_id'),
                "action": action.value,
                "simulated_drop": simulated_drop,
                "verdict_multiplier": verdict_multiplier,
                "counterfactual_reward": final_reward
            })
            
        log.info(f"Processed {len(results)} shadow records for counterfactual learning.")
        return results