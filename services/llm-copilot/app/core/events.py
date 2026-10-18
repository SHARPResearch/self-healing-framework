# Pydantic models for Component 2 event payloads

"""
Pydantic models representing the data contracts between
Component 2 (Decision Engine) and Component 5 (LLM Copilot).

These models define the EXACT schema of recovery events
that Component 2 will publish via webhook/API.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ValidationOutcome(str, Enum):
    """Possible outcomes from Component 2's Validation Layer."""
    AUTO_EXECUTE = "AUTO_EXECUTE"
    SHADOW_MODE = "SHADOW_MODE"
    BLOCKED = "BLOCKED"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TriggeringAnomaly(BaseModel):
    """The anomaly signal that triggered the decision."""
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    metric: str
    deviation_magnitude: float
    detected_at: datetime


class DependencyContext(BaseModel):
    """Dependency graph context from Component 2."""
    root_cause_service: Optional[str] = None
    blast_radius: int = Field(..., ge=0)
    risk_level: RiskLevel
    propagation_type: Optional[str] = None  # upstream | downstream | isolated


class ActionTaken(BaseModel):
    """The recovery action executed by Component 2."""
    type: str  # scale_out | restart_pod | traffic_reroute | circuit_breaker
    target: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class RecoveryEventPayload(BaseModel):
    """
    MANDATORY INPUT for Function 2 (Post-Mortem Generator).
    
    This is the complete payload sent by Component 2 after
    a recovery action is executed (or simulated in Shadow Mode).
    """
    decision_id: str
    timestamp: datetime
    service: str
    triggering_anomaly: TriggeringAnomaly
    dependency_context: DependencyContext
    rule_matched: str
    validation_outcome: ValidationOutcome
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    action_taken: ActionTaken
    execution_status: str  # SUCCESS | FAILED | SIMULATED
    recovery_time_sec: Optional[float] = None
    telemetry_snapshot_url: Optional[str] = None
    
    # Shadow Mode specific fields
    simulated_outcome: Optional[Dict[str, Any]] = None
    actual_outcome: Optional[Dict[str, Any]] = None
    verdict: Optional[str] = None


class MaskingRequest(BaseModel):
    """MANDATORY INPUT for Function 1 (Security Agent)."""
    raw_data: Any  # Can be string, dict, or list


class MaskingResponse(BaseModel):
    """MANDATORY OUTPUT for Function 1."""
    sanitized_data: Any
    status: str
    entities_scrubbed: int = 0
    leakage_detected: bool = False


class PostMortemResponse(BaseModel):
    """MANDATORY OUTPUT for Function 2."""
    decision_id: str
    markdown_report: str
    generated_at: datetime
    generation_latency_sec: float
    rag_faithfulness_score: Optional[float] = None
    status: str