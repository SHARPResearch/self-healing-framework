"""
state_assembler.py
Converts EnrichedContextPayload into a normalized numerical NumPy state vector (S_t).
This serves as the ADAPTER between LiyanaArachchi's data structure and Wijesinghe's RL model.
"""

import numpy as np
from .schema import EnrichedContextPayload, FailureType, HealthStatus, SeverityLevel

# Encoding maps to convert categorical text to numbers for RL
FAILURE_TYPE_MAP = {
    FailureType.UNKNOWN: 0,
    FailureType.MEMORY_LEAK: 1,
    FailureType.HIGH_LATENCY: 2,
    FailureType.CPU_SPIKE: 3
}

HEALTH_STATUS_MAP = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.DEGRADED: 1,
    HealthStatus.DOWN: 2,
    HealthStatus.UNKNOWN: 3
}

SEVERITY_MAP = {
    SeverityLevel.LOW: 0.25,
    SeverityLevel.MEDIUM: 0.50,
    SeverityLevel.HIGH: 0.75,
    SeverityLevel.CRITICAL: 1.00
}


def assemble_state_vector(payload: EnrichedContextPayload) -> np.ndarray:
    """
    Transforms the structured payload into a 7-dimensional normalized NumPy State Vector (S_t).
    
    S_t Features:
    [0] Failure Probability      (float: 0.0 - 1.0)
    [1] Failure Type Encoded     (int:   0 - 3)
    [2] Is Root Cause            (int:   0 or 1)
    [3] Upstream Status Encoded  (int:   0 - 3)
    [4] Downstream Impact Count  (float: normalized by /10.0)
    [5] Blast Radius Score       (float: 0.0 - 1.0)
    [6] Cooldown Active          (int:   0 or 1)
    """
    p = payload.prediction_data
    g = payload.graph_context
    i = payload.impact_assessment
    guard = payload.guardrail_status

    state = [
        float(p.failure_probability),
        float(FAILURE_TYPE_MAP.get(p.failure_type, 0)),
        1.0 if g.is_root_cause else 0.0,
        float(HEALTH_STATUS_MAP.get(g.upstream_status, 3)),
        float(min(g.downstream_impact_count / 10.0, 1.0)),  # Cap and normalize
        float(i.blast_radius_score),
        1.0 if guard.cooldown_active else 0.0
    ]

    return np.array(state, dtype=np.float32)