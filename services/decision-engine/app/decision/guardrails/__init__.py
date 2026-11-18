# services/decision-engine/app/decision/guardrails/__init__.py
"""
Public surface of the Safety Guardrails.

    from app.decision.guardrails import check, mark, GuardrailVerdict

`check(recovery_action, anomaly_id)` — return a verdict (never raises).
`mark(recovery_action, anomaly_id, decision_id)` — record side effects
                                                   after a passing verdict.
"""
from app.decision.guardrails.guardrails import check, mark
from app.decision.guardrails.verdict import (
    GuardrailCheck,
    GuardrailVerdict,
)

__all__ = ["check", "mark", "GuardrailVerdict", "GuardrailCheck"]