"""
db_reader.py
The "History Book" reader for Component 3.
This module fetches real historical data from LiyanaArachchi's Neon Postgres DB.
We use this data to train our RL (Agent) offline before it ever touches the live system.
"""
import logging
from typing import List, Dict, Any

# We use psycopg (the modern Postgres adapter for Python)
import psycopg
from psycopg.rows import dict_row

from .db import get_conn

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# 1. SHADOW RECORDS (The "What-If" History)
# ─────────────────────────────────────────────────────────────────────
def fetch_shadow_records(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetches shadow mode records. 
    Story: These are the times the system thought about doing something, 
    but didn't. We use this to teach our Puppy what WOULD have happened.
    """
    query = """
        SELECT id, decision_id, anomaly_id, service_id,
               candidate_action, confidence, risk,
               simulated_outcome, actual_outcome, verdict, learning
        FROM shadow_records
        ORDER BY created_at DESC
        LIMIT %s
    """
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (limit,))
                records = cur.fetchall()
                log.info(f"Fetched {len(records)} shadow records for offline training.")
                return records
    except Exception as e:
        log.error(f"Failed to fetch shadow records: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────
# 2. DECISION LOG (The "Rule Engine" History)
# ─────────────────────────────────────────────────────────────────────
def fetch_decision_log(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetches the Rule Engine's past decisions.
     This shows us what the "strict " (Rule Engine) did in the past.
    We need the blast_factor and centrality to build our GCN Whisper Network.
    """
    query = """
        SELECT id, anomaly_id, service_id, rule_id, action,
               action_params, detection_conf, rule_conf, final_conf,
               base_risk, blast_factor, centrality, effective_severity,
               policy_outcome, policy_reason, context
        FROM decision_log
        ORDER BY created_at DESC
        LIMIT %s
    """
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (limit,))
                records = cur.fetchall()
                log.info(f"Fetched {len(records)} decision log entries.")
                return records
    except Exception as e:
        log.error(f"Failed to fetch decision log: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────
# 3. ANOMALY EVENTS (The "Sickness" History)
# ─────────────────────────────────────────────────────────────────────
def fetch_anomaly_events(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetches raw anomaly events from Component 1.
    Story: These are the records of when a microservice got a "fever" (anomaly).
    """
    query = """
        SELECT id, service_id, service_name, team, layer,
               anomaly_score, severity, metric, actual_value, 
               expected_value, deviation_sigma, confidence, model_version,
               features, detected_at
        FROM anomaly_events
        ORDER BY detected_at DESC
        LIMIT %s
    """
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (limit,))
                records = cur.fetchall()
                log.info(f"Fetched {len(records)} anomaly events.")
                return records
    except Exception as e:
        log.error(f"Failed to fetch anomaly events: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────
# 4. ACTION HISTORY (The  Past Mistakes")
# ─────────────────────────────────────────────────────────────────────
def fetch_action_history(service_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetches the history of actions taken and their outcomes.
    Did the agent's last trick work? If he tried to SIT 5 times and failed,
    we need to know so he doesn't try it again (Conflict Penalty).
    """
    query = """
        SELECT id, decision_id, service_id, action, outcome, occurred_at
        FROM action_history
    """
    params = []
    
    # Optional filter by service_id
    if service_id:
        query += " WHERE service_id = %s"
        params.append(service_id)
        
    query += " ORDER BY occurred_at DESC LIMIT %s"
    params.append(limit)

    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                records = cur.fetchall()
                log.info(f"Fetched {len(records)} action history records.")
                return records
    except Exception as e:
        log.error(f"Failed to fetch action history: {e}")
        return []