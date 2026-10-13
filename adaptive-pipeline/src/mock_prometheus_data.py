"""
Mock Prometheus Data Generator.
Simulates realistic telemetry payloads from LiyanaArachchi's Rule-Based Engine 
for testing  demonstration purposes.
"""

import json
import random
from datetime import datetime, timezone
from typing import Dict, Any


class MockPrometheusGenerator:
    """Generates realistic EnrichedContextPayload JSON structures."""

    SERVICES = ["payment-service", "order-service", "user-service", "inventory-service"]
    FAILURE_TYPES = ["MEMORY_LEAK", "HIGH_LATENCY", "CPU_SPIKE"]
    SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    @staticmethod
    def generate_scenario(scenario_type: str = "memory_leak") -> Dict[str, Any]:
        """
        Generates a specific failure scenario payload.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        service = random.choice(MockPrometheusGenerator.SERVICES)

        if scenario_type == "memory_leak":
            return {
                "event_id": f"evt-{random.randint(1000, 9999)}",
                "timestamp": timestamp,
                "prediction_data": {
                    "service_id": service,
                    "failure_type": "MEMORY_LEAK",
                    "failure_probability": 0.88,
                    "estimated_time_to_failure_sec": 120
                },
                "graph_context": {
                    "is_root_cause": True,
                    "upstream_status": "HEALTHY",
                    "downstream_impact_count": 3,
                    "affected_downstream_services": ["order-service", "checkout-service"]
                },
                "impact_assessment": {
                    "blast_radius_score": 0.75,
                    "severity_level": "HIGH"
                },
                "guardrail_status": {
                    "cooldown_active": False,
                    "time_since_last_action_sec": 600,
                    "recent_action_count_15m": 1
                }
            }

        elif scenario_type == "high_latency":
            return {
                "event_id": f"evt-{random.randint(1000, 9999)}",
                "timestamp": timestamp,
                "prediction_data": {
                    "service_id": service,
                    "failure_type": "HIGH_LATENCY",
                    "failure_probability": 0.92,
                    "estimated_time_to_failure_sec": 60
                },
                "graph_context": {
                    "is_root_cause": False,
                    "root_cause_service_id": "database-service",
                    "upstream_status": "DEGRADED",
                    "downstream_impact_count": 5
                },
                "impact_assessment": {
                    "blast_radius_score": 0.90,
                    "severity_level": "CRITICAL"
                },
                "guardrail_status": {
                    "cooldown_active": True,
                    "time_since_last_action_sec": 30,
                    "recent_action_count_15m": 4
                }
            }
        
        else: # Default / Healthy
            return {
                "event_id": f"evt-{random.randint(1000, 9999)}",
                "timestamp": timestamp,
                "prediction_data": {
                    "service_id": service,
                    "failure_type": "UNKNOWN",
                    "failure_probability": 0.10,
                    "estimated_time_to_failure_sec": 3600
                },
                "graph_context": {
                    "is_root_cause": True,
                    "upstream_status": "HEALTHY",
                    "downstream_impact_count": 0
                },
                "impact_assessment": {
                    "blast_radius_score": 0.05,
                    "severity_level": "LOW"
                },
                "guardrail_status": {
                    "cooldown_active": False,
                    "time_since_last_action_sec": 9999,
                    "recent_action_count_15m": 0
                }
            }

    @staticmethod
    def get_json_string(scenario_type: str = "memory_leak") -> str:
        """Returns the payload as a formatted JSON string for API simulation."""
        data = MockPrometheusGenerator.generate_scenario(scenario_type)
        return json.dumps(data, indent=4)


if __name__ == "__main__":
    print("--- Memory Leak Scenario ---")
    print(MockPrometheusGenerator.get_json_string("memory_leak"))
    print("\n--- High Latency Scenario ---")
    print(MockPrometheusGenerator.get_json_string("high_latency"))