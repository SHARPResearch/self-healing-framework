# NER + regex patterns

"""
PII Detector using regex patterns + spaCy NER.
Identifies sensitive entities in telemetry data.
"""
import re
from typing import List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class PIIEntity:
    """Represents a detected PII entity."""
    entity_type: str
    value: str
    start: int
    end: int
    confidence: float


class PIIDetector:
    """
    Detects PII patterns in text using regex + optional NER.
    
    Supported patterns:
    - IPv4 addresses
    - Bearer tokens / API keys
    - Email addresses
    - Credit card numbers
    - Phone numbers
    - Internal hostnames
    """

    PATTERNS: Dict[str, str] = {
        "IP_V4": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
        "IP_V6": r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}",
        "BEARER_TOKEN": r"(?i)bearer\s+[a-z0-9\-._~+/]+=*",
        "API_KEY": r"(?i)(api[_-]?key|token|secret|password|auth)[\"']?\s*[:=]\s*[\"']?([a-z0-9\-._~+/]{16,})",
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
        "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "INTERNAL_HOST": r"\b[a-z0-9-]+(?:\.internal|\.local|\.svc\.cluster\.local)\b",
        "JWT_TOKEN": r"eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+",
    }

    def detect(self, text: str) -> List[PIIEntity]:
        """Detect all PII entities in the given text."""
        entities: List[PIIEntity] = []
        for entity_type, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, text):
                entities.append(
                    PIIEntity(
                        entity_type=entity_type,
                        value=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        confidence=1.0,
                    )
                )
        # Sort by position for consistent replacement
        return sorted(entities, key=lambda e: e.start)

    def get_summary(self, entities: List[PIIEntity]) -> Dict[str, int]:
        """Get count summary by entity type."""
        summary: Dict[str, int] = {}
        for entity in entities:
            summary[entity.entity_type] = summary.get(entity.entity_type, 0) + 1
        return summary