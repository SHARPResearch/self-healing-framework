"""
hybrid_arbitration.py
The "Traffic Cop" for Component 3. 
Implements the Hybrid     Arbitration logic defined in Component 3 §8.2.
Decides whether the Rule Engine or the RL Engine gets to execute an action.
"""
from enum import Enum
from typing import Optional

class PolicyOutcome(str, Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    SHADOW_MODE = "SHADOW_MODE"
    BLOCK = "BLOCK"
    HUMAN_LOOP = "HUMAN_LOOP"

class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class HybridArbitrator:
    def decide(
        self,
        rule_action: str,
        rule_confidence: float,
        rule_outcome: PolicyOutcome,
        rl_action: str,
        rl_confidence: float,
        severity: SeverityLevel
    ) -> dict:
        """
        Executes the Decision Policy Matrix from Component 3 §8.2.
        Returns the winning action, the winning engine, and the reasoning.
        """
        # 1. Safety Veto: RL cannot override a safety block or human loop
        if rule_outcome in (PolicyOutcome.HUMAN_LOOP, PolicyOutcome.BLOCK):
            return {
                "winning_action": rule_action,
                "winning_engine": "RULE_ENGINE",
                "reason": f"Safety veto: Rule engine outcome is {rule_outcome.value}"
            }

        # 2. Time-Critical: High severity always goes to the deterministic Rule Engine
        if severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH):
            return {
                "winning_action": rule_action,
                "winning_engine": "RULE_ENGINE",
                "reason": f"Time-critical: Severity is {severity.value}"
            }

        # 3. RL Uncertainty: If RL is unsure, fall back to rules
        if rl_confidence < 0.60:
            return {
                "winning_action": rule_action,
                "winning_engine": "RULE_ENGINE",
                "reason": f"RL uncertain: Confidence {rl_confidence} < 0.60"
            }

        # 4. Rule Uncertainty: If Rule is unsure but RL is confident, let RL drive
        if rule_confidence < 0.60 and rl_confidence >= 0.60:
            return {
                "winning_action": rl_action,
                "winning_engine": "RL_ENGINE",
                "reason": f"Rule uncertain: Rule conf {rule_confidence} < 0.60, RL conf {rl_confidence} >= 0.60"
            }

        # 5. Adaptive Signal: Medium severity is where RL shines
        if severity == SeverityLevel.MEDIUM:
            return {
                "winning_action": rl_action,
                "winning_engine": "RL_ENGINE",
                "reason": f"Adaptive signal: Severity is MEDIUM and RL is confident"
            }

        # 6. Default Fallback
        return {
            "winning_action": rule_action,
            "winning_engine": "RULE_ENGINE",
            "reason": "Default fallback to Rule Engine"
        }