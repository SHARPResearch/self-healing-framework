"""
Reporting Agent API Routes — FUNCTION 2 of PP1.
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.core.events import RecoveryEventPayload, PostMortemResponse
from app.agents.reporting.postmortem_gen import postmortem_generator

router = APIRouter(prefix="/api/postmortem", tags=["Reporting Agent"])


@router.post("/generate", response_model=PostMortemResponse, summary="Generate Post-Mortem Report")
async def generate_postmortem(event: RecoveryEventPayload):
    """
    ## Automated Post-Mortem Generator
    
    **Purpose:** Consumes recovery events from Component 2 and generates 
    a professional Markdown incident report.
    
    **Mandatory Input:** `recovery_event_payload` 
    **Mandatory Output:** `markdown_report` (Structured Markdown string)
    """
    try:
        result = await postmortem_generator.generate(event)
        return PostMortemResponse(**result)
    except Exception as e:
        logger.exception("Post-mortem generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", summary="List All Post-Mortems")
async def list_postmortems():
    """
    Returns a list of all generated post-mortem reports.
    (Currently returns mock data for PP1 demonstration)
    """
    return {
        "reports": [
            {
                "decision_id": "dec-2026-10-16-0001",
                "service": "payment-svc",
                "status": "SUCCESS",
                "generated_at": "2026-10-16T10:16:00Z"
            }
        ]
    }


@router.get("/{decision_id}", summary="Get Specific Post-Mortem by ID")
async def get_postmortem(decision_id: str):
    """
    Retrieves a specific post-mortem report by its decision_id.
    """
    # Mock response for PP1 demonstration
    return {
        "decision_id": decision_id,
        "markdown_report": f"# Incident Post-Mortem Report: {decision_id}\n\n## Summary\nThis is a sample post-mortem report generated for demonstration purposes.",
        "status": "SUCCESS",
        "generation_latency_sec": 2.5
    }