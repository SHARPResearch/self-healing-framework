"""
Security Agent API Routes — FUNCTION 1 of PP1.
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.core.events import MaskingRequest, MaskingResponse
from app.agents.security.masking import masking_agent

router = APIRouter(prefix="/api/security", tags=["Security Agent"])


@router.post("/mask", response_model=MaskingResponse, summary="Systemic Masking Guardrail")
async def mask_sensitive_telemetry(request: MaskingRequest):
    """
    ## FUNCTION 1: Systemic Masking Guardrail (Security Agent)
    
    **Purpose:** Ensures zero data leakage by sanitizing raw telemetry 
    before LLM processing.
    
    **Mandatory Input:** `raw_data` (String or JSON containing raw logs, metrics, or chat input)
    
    **Mandatory Output:** `sanitized_data` (String/JSON with PII, internal IPs, 
    and bearer tokens replaced by `[REDACTED_*]`)
    """
    try:
        result = masking_agent.process(request.raw_data)
        return MaskingResponse(**result)
    except Exception as e:
        logger.exception("Masking endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", summary="Security Agent Statistics")
async def get_masking_stats():
    """Return processing statistics for evaluation metrics."""
    return masking_agent.get_stats()