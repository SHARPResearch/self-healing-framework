"""
Decision module — Severity, Action Selection, and (later) Validation.

Public API:
    SeverityBreakdown, ActionSelection, Decision, PolicyOutcome  (models)
    compute_severity                                              (severity)
    select_action                                                 (action_selector)
"""
from app.decision.models import (
    ActionSelection,
    Decision,
    PolicyOutcome,
    SeverityBreakdown,
)
from app.decision.severity import compute_severity
from app.decision.action_selector import select_action

__all__ = [
    "SeverityBreakdown",
    "ActionSelection",
    "Decision",
    "PolicyOutcome",
    "compute_severity",
    "select_action",
]