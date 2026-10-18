"""
Security Agent — Systemic Masking Guardrail.

This is FUNCTION 1 for PP1.
It intercepts ALL data before it reaches the LLM and scrubs PII.

MANDATORY INPUT:  raw_telemetry_data (str | dict | list)
MANDATORY OUTPUT: sanitized_telemetry_data (same type, zero leakage)
"""
import json
from typing import Any, Dict, Union, List
from loguru import logger

from app.agents.security.pii_detector import PIIDetector, PIIEntity
from app.agents.security.token_scrubber import TokenScrubber


class SecurityMaskingAgent:
    """
    Systemic Masking Guardrail Agent.
    
    Enforces ZERO LEAKAGE policy before any data reaches external LLM APIs.
    Combines regex-based PII detection with specialized token scrubbing.
    """

    def __init__(self):
        self.pii_detector = PIIDetector()
        self.token_scrubber = TokenScrubber()
        self._stats = {"total_processed": 0, "total_entities_scrubbed": 0}

    def mask_text(self, text: str) -> tuple[str, List[PIIEntity]]:
        """Scrub sensitive patterns from a raw string."""
        if not text:
            return text, []

        # Step 1: Detect PII entities
        entities = self.pii_detector.detect(text)

        # Step 2: Replace detected entities (reverse order to preserve positions)
        masked = text
        for entity in reversed(entities):
            replacement = f"[REDACTED_{entity.entity_type}]"
            masked = masked[: entity.start] + replacement + masked[entity.end :]

        # Step 3: Apply specialized token scrubbing
        masked = self.token_scrubber.scrub(masked)

        return masked, entities

    def mask_json(self, data: Union[Dict, List, str, Any]) -> tuple[Any, int]:
        """
        Recursively scrub sensitive data from JSON/Dict/List objects.
        Returns (sanitized_data, total_entities_scrubbed).
        """
        total_scrubbed = 0

        if isinstance(data, str):
            masked, entities = self.mask_text(data)
            return masked, len(entities)

        elif isinstance(data, dict):
            result = {}
            for key, value in data.items():
                masked_value, count = self.mask_json(value)
                result[key] = masked_value
                total_scrubbed += count
            return result, total_scrubbed

        elif isinstance(data, list):
            result = []
            for item in data:
                masked_item, count = self.mask_json(item)
                result.append(masked_item)
                total_scrubbed += count
            return result, total_scrubbed

        # Primitive types (int, float, bool, None) pass through
        return data, 0

    def process(self, raw_data: Any) -> Dict[str, Any]:
        """
        Main entry point — FUNCTION 1 of PP1.
        
        Args:
            raw_data: Raw telemetry data (string, dict, or list)
        
        Returns:
            Dict with sanitized_data, status, entities_scrubbed, leakage_detected
        """
        try:
            sanitized, entities_count = self.mask_json(raw_data)

            self._stats["total_processed"] += 1
            self._stats["total_entities_scrubbed"] += entities_count

            # Verify zero leakage (re-scan the output)
            verification_text = json.dumps(sanitized) if not isinstance(sanitized, str) else sanitized
            remaining_entities = self.pii_detector.detect(verification_text)
            leakage_detected = len(remaining_entities) > 0

            if leakage_detected:
                logger.error(f"LEAKAGE DETECTED after masking! {len(remaining_entities)} entities remain.")

            return {
                "sanitized_data": sanitized,
                "status": "SUCCESS_ZERO_LEAKAGE" if not leakage_detected else "FAILURE_LEAKAGE_DETECTED",
                "entities_scrubbed": entities_count,
                "leakage_detected": leakage_detected,
            }

        except Exception as e:
            logger.exception("Security masking failed")
            return {
                "sanitized_data": None,
                "status": f"ERROR: {str(e)}",
                "entities_scrubbed": 0,
                "leakage_detected": True,  # Fail-safe: assume leakage on error
            }

    def get_stats(self) -> Dict[str, int]:
        """Return processing statistics for evaluation metrics."""
        return self._stats.copy()


# Singleton instance
masking_agent = SecurityMaskingAgent()