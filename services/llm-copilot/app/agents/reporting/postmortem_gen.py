"""
Reporting Agent — Generates structured Markdown Post-Mortem reports.

This is FUNCTION 2 for PP1.

MANDATORY INPUT:  recovery_event_payload (from Component 2)
MANDATORY OUTPUT: markdown_report (structured incident documentation)
"""
import time
from datetime import datetime
from typing import Dict, Any
from loguru import logger

from app.core.events import RecoveryEventPayload
from app.agents.rca.rca_agent import rca_agent
from app.agents.security.masking import masking_agent
from app.services.llm_client import llm_client
from app.services.decision_engine_client import decision_engine_client


POSTMORTEM_SYSTEM_PROMPT = """You are a senior DevOps engineer writing a professional incident post-mortem report.
Generate a comprehensive Markdown post-mortem with these sections:

# Incident Post-Mortem Report

## Executive Summary
(1-2 paragraph overview)

## Root Cause Analysis
(Detailed technical analysis)

## Impact Assessment
- Services affected
- Blast radius
- Duration
- User impact

## Timeline
(Chronological events with timestamps)

## Recovery Actions Taken
(What the automated system did)

## Metrics During Incident
(Key telemetry observations)

## Resolution Verification
(How we confirmed recovery)

## Recommendations & Preventive Measures
(Actionable items to prevent recurrence)

## Lessons Learned
(Key takeaways)

Use professional, clear language. Include code blocks for commands/queries where relevant."""


class PostMortemGenerator:
    """
    Asynchronous Reporting Agent — generates Markdown post-mortems
    triggered by recovery events from Component 2.
    """

    async def generate(self, event: RecoveryEventPayload) -> Dict[str, Any]:
        """
        Main entry point — FUNCTION 2 of PP1.
        
        Args:
            event: Recovery event payload from Component 2
        
        Returns:
            Dict with markdown_report, latency, status
        """
        start_time = time.time()
        logger.info(f"Generating post-mortem for decision {event.decision_id}")

        try:
            # Step 1: Fetch extended telemetry from Component 2
            telemetry_context = await decision_engine_client.get_telemetry_history(event.decision_id)
            if not telemetry_context:
                telemetry_context = {"note": "Extended telemetry unavailable, using event data only"}

            # Step 2: Run RCA Agent to get root cause analysis
            rca_result = await rca_agent.analyze(event, telemetry_context)

            # Step 3: Generate full Markdown post-mortem
            markdown_report = await self._generate_markdown(event, rca_result, telemetry_context)

            # Step 4: Final security verification (mask the output too)
            final_report = masking_agent.process(markdown_report)["sanitized_data"]

            latency = time.time() - start_time
            logger.info(f"Post-mortem generated in {latency:.2f}s for {event.decision_id}")

            return {
                "decision_id": event.decision_id,
                "markdown_report": final_report,
                "generated_at": datetime.utcnow().isoformat(),
                "generation_latency_sec": round(latency, 3),
                "rag_faithfulness_score": None,  # Populated by evaluation agent
                "status": "SUCCESS",
            }

        except Exception as e:
            logger.exception(f"Post-mortem generation failed for {event.decision_id}")
            latency = time.time() - start_time
            return {
                "decision_id": event.decision_id,
                "markdown_report": f"# Post-Mortem Generation Failed\n\nError: {str(e)}",
                "generated_at": datetime.utcnow().isoformat(),
                "generation_latency_sec": round(latency, 3),
                "rag_faithfulness_score": None,
                "status": "ERROR",
            }

    async def _generate_markdown(
        self,
        event: RecoveryEventPayload,
        rca_result: Dict[str, Any],
        telemetry_context: Dict[str, Any],
    ) -> str:
        """Generate the full Markdown post-mortem via LLM."""
        # Mask all inputs before sending to LLM
        # masked_event = masking_agent.process(event.model_dump())["sanitized_data"]
        masked_event = masking_agent.process(event.model_dump(mode='json'))["sanitized_data"]
        masked_rca = masking_agent.process(rca_result)["sanitized_data"]
        masked_telemetry = masking_agent.process(telemetry_context)["sanitized_data"]

        prompt = f"""Generate a professional incident post-mortem report based on:

## RECOVERY EVENT
{masked_event}

## ROOT CAUSE ANALYSIS
{masked_rca}

## TELEMETRY CONTEXT
{masked_telemetry}

Produce a comprehensive Markdown post-mortem following the structure in your instructions."""

        return llm_client.generate(
            prompt=prompt,
            system_prompt=POSTMORTEM_SYSTEM_PROMPT,
            temperature=0.3,
        )


# Singleton
postmortem_generator = PostMortemGenerator()