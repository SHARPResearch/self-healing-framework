# Orchestrator Agent - routes requests

"""
Orchestrator Router - Routes requests to appropriate agents.
"""
from typing import Dict, Any
from loguru import logger

from app.agents.conversational.rag_pipeline import rag_pipeline
from app.agents.reporting.postmortem_gen import postmortem_generator
from app.agents.rca.rca_agent import rca_agent
from app.agents.security.masking import masking_agent


class OrchestratorRouter:
    """Routes requests to appropriate specialized agents."""

    async def route_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route incoming request to appropriate agent.
        
        Args:
            request: Request dictionary with type and payload
        
        Returns:
            Response from the appropriate agent
        """
        try:
            request_type = request.get("type", "unknown")
            payload = request.get("payload", {})
            
            logger.info(f" Routing request type: {request_type}")
            
            if request_type == "chat":
                return await self._handle_chat(payload)
            elif request_type == "postmortem":
                return await self._handle_postmortem(payload)
            elif request_type == "rca":
                return await self._handle_rca(payload)
            elif request_type == "mask":
                return self._handle_mask(payload)
            else:
                return {"error": f"Unknown request type: {request_type}"}
                
        except Exception as e:
            logger.error(f" Routing failed: {e}")
            return {"error": str(e)}

    async def _handle_chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat/query requests."""
        query = payload.get("query", "")
        context = payload.get("context", {})
        
        result = await rag_pipeline.process_query(query, context)
        return {
            "type": "chat_response",
            "data": result
        }

    async def _handle_postmortem(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle post-mortem generation requests."""
        from app.core.events import RecoveryEventPayload
        
        event = RecoveryEventPayload(**payload)
        result = await postmortem_generator.generate(event)
        
        return {
            "type": "postmortem_response",
            "data": result
        }

    async def _handle_rca(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle RCA requests."""
        from app.core.events import RecoveryEventPayload
        
        event = RecoveryEventPayload(**payload)
        telemetry_context = payload.get("telemetry_context", {})
        
        result = await rca_agent.analyze(event, telemetry_context)
        return {
            "type": "rca_response",
            "data": result
        }

    def _handle_mask(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle masking requests."""
        raw_data = payload.get("raw_data")
        result = masking_agent.process(raw_data)
        
        return {
            "type": "mask_response",
            "data": result
        }


# Singleton instance
orchestrator = OrchestratorRouter()