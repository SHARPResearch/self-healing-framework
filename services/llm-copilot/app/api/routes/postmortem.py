"""
Reporting Agent API Routes — FUNCTION 2 of PP1.
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.core.events import RecoveryEventPayload, PostMortemResponse
from app.agents.reporting.postmortem_gen import postmortem_generator

router = APIRouter(prefix="/api/postmortem", tags=["Reporting Agent (Function 2)"])


@router.post("/generate", response_model=PostMortemResponse, summary="Generate Post-Mortem Report")
async def generate_postmortem(event: RecoveryEventPayload):
    """
    ## FUNCTION 2: Automated Post-Mortem Generator (Reporting + RCA Agents)
    
    **Purpose:** Consumes recovery events from Component 2 and generates 
    a professional Markdown incident report.
    
    **Mandatory Input:** `recovery_event_payload` (JSON from Component 2 containing: 
    service_name, anomaly_score, root_cause, actions_taken, timestamps, etc.)
    
    **Mandatory Output:** `markdown_report` (Structured Markdown string with 
    Root Cause Analysis, timeline, impact, and recommendations)
    """
    try:
        result = await postmortem_generator.generate(event)
        return PostMortemResponse(**result)
    except Exception as e:
        logger.exception("Post-mortem generation failed")
        raise HTTPException(status_code=500, detail=str(e))