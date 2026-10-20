"""
RCA Agent — Analyzes recovery events and produces structured
Root Cause Analysis before post-mortem generation.
"""
from typing import Dict, Any
from loguru import logger

from app.core.events import RecoveryEventPayload
from app.services.llm_client import llm_client
from app.agents.security.masking import masking_agent


RCA_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) performing Root Cause Analysis.
Analyze the provided recovery event data and produce a structured RCA with:
1. INCIDENT SUMMARY (1-2 sentences)
2. ROOT CAUSE (technical explanation)
3. BLAST RADIUS IMPACT (which services were affected)
4. RECOVERY ACTION TAKEN (what the system did)
5. TIMELINE (chronological sequence)
6. RECOMMENDATIONS (preventive measures)

Be precise, technical, and factual. Use Markdown formatting."""


class RCAAgent:
    """Performs Root Cause Analysis on recovery events."""

    async def analyze(self, event: RecoveryEventPayload, telemetry_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a recovery event and produce structured RCA.
        
        Args:
            event: The recovery event payload from Component 2
            telemetry_context: Extended telemetry data
        
        Returns:
            Dict with RCA analysis
        """
        # Step 1: Mask sensitive data BEFORE sending to LLM
        # masked_event = masking_agent.process(event.model_dump())["sanitized_data"]
        masked_event = masking_agent.process(event.model_dump(mode='json'))["sanitized_data"]
        masked_telemetry = masking_agent.process(telemetry_context)["sanitized_data"]

        # Step 2: Build RCA prompt
        prompt = self._build_rca_prompt(masked_event, masked_telemetry)

        # Step 3: Generate RCA via LLM
        try:
            rca_text = llm_client.generate(
                prompt=prompt,
                system_prompt=RCA_SYSTEM_PROMPT,
                temperature=0.2,
            )
            logger.info(f"RCA generated for decision {event.decision_id}")
            return {
                "decision_id": event.decision_id,
                "rca_analysis": rca_text,
                "root_cause_service": event.dependency_context.root_cause_service or event.service,
                "blast_radius": event.dependency_context.blast_radius,
            }
        except Exception as e:
            logger.error(f"RCA generation failed: {e}")
            return {
                "decision_id": event.decision_id,
                "rca_analysis": f"RCA generation failed: {str(e)}",
                "root_cause_service": event.service,
                "blast_radius": event.dependency_context.blast_radius,
            }

    def _build_rca_prompt(self, masked_event: Dict, masked_telemetry: Dict) -> str:
        """Construct the RCA prompt from masked data."""
        return f"""
Analyze the following recovery event and produce a structured Root Cause Analysis.

## RECOVERY EVENT DATA
{masked_event}

## EXTENDED TELEMETRY CONTEXT
{masked_telemetry}

Provide your RCA in Markdown format with the sections outlined in your instructions.
"""


# Singleton
rca_agent = RCAAgent()