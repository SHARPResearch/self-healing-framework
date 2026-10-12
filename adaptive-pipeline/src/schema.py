"""
schema.py
Data Contract for incoming Enriched Context Payload.
Designed with flexibility to tolerate future changes from LiyanaArachchi.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# --- Enum Mappings with Fallbacks ---

class FailureType(str, Enum):
    MEMORY_LEAK = "MEMORY_LEAK"
    HIGH_LATENCY = "HIGH_LATENCY"
    CPU_SPIKE = "CPU_SPIKE"
    UNKNOWN = "UNKNOWN"


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# --- Sub-Payload Models ---

class PredictionData(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore unexpected extra fields from LiyanaArachchi
    
    service_id: str = Field(default="unknown-service", description="Target microservice identifier")
    failure_type: FailureType = Field(default=FailureType.UNKNOWN, description="Type of failure predicted")
    failure_probability: float = Field(default=0.5, ge=0.0, le=1.0, description="Predicted probability (0.0 to 1.0)")
    estimated_time_to_failure_sec: int = Field(default=300, ge=0, description="Estimated seconds until failure")


class GraphContext(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    is_root_cause: bool = Field(default=True, description="True if service is the failure origin")
    root_cause_service_id: Optional[str] = Field(default=None, description="Actual root cause service ID if false")
    upstream_status: HealthStatus = Field(default=HealthStatus.HEALTHY, description="Health state of upstream dependencies")
    downstream_impact_count: int = Field(default=0, ge=0, description="Number of dependent services affected")
    affected_downstream_services: List[str] = Field(default_factory=list, description="List of downstream service IDs")


class ImpactAssessment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    blast_radius_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Proportional system impact (0.0 to 1.0)")
    severity_level: SeverityLevel = Field(default=SeverityLevel.MEDIUM, description="Categorical impact severity")


class GuardrailStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    cooldown_active: bool = Field(default=False, description="True if action execution is on cooldown")
    time_since_last_action_sec: int = Field(default=9999, ge=0, description="Seconds elapsed since last recovery")
    recent_action_count_15m: int = Field(default=0, ge=0, description="Number of actions taken in last 15 mins")


# --- Master Enriched Context Payload ---

class EnrichedContextPayload(BaseModel):
    """
    Master payload schema passed from LiyanaArachchi's engine to my RL engine.
    """
    model_config = ConfigDict(extra="ignore")
    
    event_id: str = Field(default="evt-0000", description="Unique prediction event identifier")
    timestamp: str = Field(default="1970-01-01T00:00:00Z", description="ISO format timestamp")
    prediction_data: PredictionData = Field(default_factory=PredictionData)
    graph_context: GraphContext = Field(default_factory=GraphContext)
    impact_assessment: ImpactAssessment = Field(default_factory=ImpactAssessment)
    guardrail_status: GuardrailStatus = Field(default_factory=GuardrailStatus)