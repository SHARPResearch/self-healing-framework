"""
shadow_simulator.py
The "Imagination Engine" for Component 3.
Provides fallback simulated outcomes when the database has no historical shadow records.
"""
from .dueling_dqn import RecoveryAction

class ShadowSimulator:
    # Estimated anomaly drop for each action based on standard microservice behavior
    ACTION_IMPACT_ESTIMATES = {
        RecoveryAction.RESTART_POD: 0.40,
        RecoveryAction.SCALE_UP: 0.25,
        RecoveryAction.FLUSH_CACHE: 0.15,
        RecoveryAction.ROLLBACK: 0.50,
        RecoveryAction.NO_ACTION: 0.00,
        RecoveryAction.OPEN_CIRCUIT: 0.30,
    }

    def estimate_anomaly_drop(self, action: RecoveryAction) -> float:
        """
        Returns a simulated anomaly drop for a given action.
        Used as a fallback when real shadow_records are unavailable.
        """
        return self.ACTION_IMPACT_ESTIMATES.get(action, 0.10) # Default small drop

    def is_simulated_regression(self, action: RecoveryAction, current_score: float) -> bool:
        """
        Heuristic: If the score is already very low (< 0.1), any heavy action 
        (like RESTART_POD) might cause a regression due to cold-start latency.
        """
        if current_score < 0.1 and action == RecoveryAction.RESTART_POD:
            return True
        return False