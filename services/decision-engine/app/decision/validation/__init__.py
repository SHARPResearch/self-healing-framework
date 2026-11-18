# services/decision-engine/app/decision/validation/__init__.py
"""
Public surface of the Validation Layer.

    from app.decision.validation import validate, ValidationResult
"""
from app.decision.validation.result import (
    ConfidenceBreakdown,
    ConflictReport,
    ValidationResult,
)
from app.decision.validation.validator import validate

__all__ = [
    "validate",
    "ValidationResult",
    "ConfidenceBreakdown",
    "ConflictReport",
]