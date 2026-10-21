import pytest

from app.notifications import emailer
from app.notifications.emailer import (
    _anomaly_body,
    _anomaly_subject,
    _decision_body,
    _decision_subject,
)


def test_anomaly_email_uses_sharp_branding_and_escapes_values():
    anomaly = {
        "id": "AN-123",
        "service_id": "svc-api",
        "service_name": "<api>",
        "severity": "critical",
        "metric": "error_rate",
        "actual_value": 0.98,
        "expected_value": 0.02,
        "anomaly_score": 0.9876,
        "detected_at": "2026-10-21T12:00:00Z",
    }

    text, html = _anomaly_body(anomaly)

    assert _anomaly_subject(anomaly) == "[SHARP] Anomaly detected: <api> (CRITICAL)"
    assert "SHARP — Automated Recovery Framework" in text
    assert "Observed value: 0.98" in text
    assert "src=\"cid:sharp-favicon\"" in html
    assert "Anomaly score" in html
    assert "&lt;api&gt;" in html
    assert "<api>" not in html


def test_decision_email_includes_policy_and_recovery_details():
    decision = {
        "service_id": "svc-api",
        "action": "SCALE_OUT",
        "action_params": {"replicas": 2},
        "policy": {"outcome": "APPROVED", "reason": "within limits"},
        "confidence": {"final": 0.92},
        "severity": {"effective_severity": 0.81},
        "blast_factor": 0.25,
        "rule_id": "scale-on-critical",
        "rule_version": 3,
        "anomaly_id": "AN-123",
        "decision_id": "DEC-456",
    }

    text, html = _decision_body(decision, None)

    assert _decision_subject(decision, None) == "[SHARP] Recovery decision: SCALE_OUT on svc-api"
    assert "Policy outcome: APPROVED (within limits)" in text
    assert "SHARP — Automated Recovery Framework" in text
    assert "Decision ID" in html
    assert "Automated recovery notifications" in html
    assert "cid:sharp-favicon" in html


@pytest.mark.asyncio
async def test_send_embeds_inline_logo_and_uses_branded_sender(monkeypatch):
    import aiosmtplib

    messages = []

    async def capture_send(message, **kwargs):
        messages.append(message)

    monkeypatch.setattr(emailer.settings, "SMTP_USER", "alerts@example.com")
    monkeypatch.setattr(emailer.settings, "SMTP_PASSWORD", "test-password")
    monkeypatch.setattr(emailer.settings, "SMTP_FROM", "alerts@example.com")
    monkeypatch.setattr(aiosmtplib, "send", capture_send)

    sent, error = await emailer._send(
        "operator@example.com",
        "Test",
        "Plain text",
        '<img src="cid:sharp-favicon">',
    )

    assert sent is True
    assert error is None
    message = messages[0]
    assert message["From"].addresses[0].display_name == "SHARP — Automated Recovery Framework"
    html_part = next(part for part in message.walk() if part.get_content_type() == "text/html")
    logo_part = next(part for part in message.walk() if part.get_content_type() == "image/png")
    assert "cid:sharp-favicon" in html_part.get_content()
    assert logo_part["Content-ID"] == "<sharp-favicon>"
    assert logo_part["Content-Disposition"].content_disposition == "inline"
