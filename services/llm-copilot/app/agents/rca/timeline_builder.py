# Builds incident timeline

"""
Timeline Builder - Builds incident timeline from recovery events.
"""
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger

class TimelineBuilder:
    """Constructs a chronological timeline of the incident for the post-mortem."""

    def build(self, event_payload: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Build a structured timeline from the Component 2 recovery event.
        """
        timeline = []
        
        # 1. Anomaly Detected
        detected_at = event_payload.get("triggering_anomaly", {}).get("detected_at", "Unknown")
        timeline.append({
            "time": str(detected_at),
            "event": "Anomaly Detected",
            "detail": f"Metric: {event_payload.get('triggering_anomaly', {}).get('metric', 'unknown')}, "
                      f"Score: {event_payload.get('triggering_anomaly', {}).get('anomaly_score', 0)}"
        })

        # 2. Decision Made
        timeline.append({
            "time": str(event_payload.get("timestamp", "Unknown")),
            "event": "Decision Engine Triggered",
            "detail": f"Rule Matched: {event_payload.get('rule_matched', 'unknown')}, "
                      f"Outcome: {event_payload.get('validation_outcome', 'unknown')}"
        })

        # 3. Action Taken
        action = event_payload.get("action_taken", {})
        timeline.append({
            "time": str(event_payload.get("timestamp", "Unknown")), # Approximate
            "event": "Recovery Action Executed",
            "detail": f"Action: {action.get('type', 'unknown')} on target: {action.get('target', 'unknown')}"
        })

        # 4. Resolution
        status = event_payload.get("execution_status", "Unknown")
        recovery_time = event_payload.get("recovery_time_sec", "N/A")
        timeline.append({
            "time": "Post-Action",
            "event": f"Resolution Status: {status}",
            "detail": f"Recovery Time: {recovery_time} seconds"
        })

        logger.info(f"Built timeline with {len(timeline)} events")
        return timeline

# Singleton instance
timeline_builder = TimelineBuilder()