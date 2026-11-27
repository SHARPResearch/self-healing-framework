"""Read training data from Component 2's Neon DB."""
import json
from .db import get_conn

def fetch_shadow_records(limit: int = 100) -> list[dict]:
    """Fetch shadow_records for counterfactual reward pre-training."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, decision_id, anomaly_id, service_id,
                       candidate_action, confidence, risk,
                       simulated_outcome, actual_outcome, verdict, learning
                FROM shadow_records
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()

def fetch_decision_log(limit: int = 100) -> list[dict]:
    """Fetch decision_log for action history and arbitration baselines."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, anomaly_id, service_id, rule_id, action,
                       action_params, detection_conf, rule_conf, final_conf,
                       base_risk, blast_factor, centrality, effective_severity,
                       policy_outcome, policy_reason, context
                FROM decision_log
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()