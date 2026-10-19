# Async listener for Component (Dession Engine)

"""
Event Listener - Async listener for Component 2 recovery events.
"""
from typing import Dict, Any
from loguru import logger

from app.agents.orchestrator.router import orchestrator

async def handle_recovery_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background listener that processes a Component 2 recovery event 
    and routes it through the multi-agent pipeline to generate a post-mortem.
    """
    logger.info(f"Event Listener: Received recovery event for {payload.get('decision_id')}")
    
    try:
        # Route through the orchestrator to ensure Security -> RCA -> Reporting -> Evaluation
        result = await orchestrator.handle("postmortem", payload)
        
        if result.get("status") == "success":
            logger.info(f"Post-mortem successfully generated for {payload.get('decision_id')}")
        else:
            logger.warning(f"Post-mortem generation had issues: {result.get('errors')}")
            
        return result
        
    except Exception as e:
        logger.error(f"Event Listener failed: {e}")
        return {"status": "error", "error": str(e)}