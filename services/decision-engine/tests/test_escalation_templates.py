# services/decision-engine/tests/test_escalation_templates.py
from __future__ import annotations

from app.decision.escalation.queue import Escalation, EscalationStatus
from app.decision.escalation import templates


def _esc(attempt=0) -> Escalation:
    return Escalation(
        id="ESC-1", decision_id="DEC-1",
        anomaly_id="ANM-1", service_id="auth-service",
        status=EscalationStatus.AWAITING_HUMAN,
        attempt=attempt,
    )


def _decision():
    return {
        "action": "RESTART_POD",
        "base_risk": "HIGH",
        "confidence": {"final": 0.71},
        "severity": {"label": "HIGH", "effective_severity": 1.62},
    }


def _anomaly():
    return {"service_name": "auth-service", "id": "ANM-1"}


def test_initial_template():
    s, t, h = templates.initial(_esc(), _decision(), _anomaly())
    assert "Human approval required" in s
    assert "attempt 1 of 3" in t
    assert "ESC-1" in t
    assert "<html" in h


def test_reminder_template():
    s, t, h = templates.reminder(_esc(1), _decision(), _anomaly())
    assert "REMINDER" in s
    assert "attempt 2 of 3" in t


def test_final_template():
    s, t, h = templates.final_failure(_esc(2), _decision(), _anomaly())
    assert "MANUAL INTERVENTION" in s
    assert "attempt 3 of 3" in t
    assert "MANUAL_REQUIRED" in t