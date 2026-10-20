"""
Comprehensive tests for the Security Agent (Function 1).
Validates the ZERO LEAKAGE guarantee.
"""
import pytest
from app.agents.security.masking import masking_agent


class TestSecurityMaskingAgent:
    """Test suite for Function 1: Systemic Masking Guardrail."""

    def test_masks_ipv4_addresses(self):
        raw = "Request from 192.168.1.100 to 10.0.0.1 failed"
        result = masking_agent.process(raw)
        assert "192.168.1.100" not in result["sanitized_data"]
        assert "10.0.0.1" not in result["sanitized_data"]
        assert "[REDACTED_IP_V4]" in result["sanitized_data"]
        assert result["status"] == "SUCCESS_ZERO_LEAKAGE"
        assert result["leakage_detected"] is False

    def test_masks_bearer_tokens(self):
        raw = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = masking_agent.process(raw)
        assert "eyJhbGci" not in result["sanitized_data"]
        assert "[REDACTED_BEARER_TOKEN]" in result["sanitized_data"]

    def test_masks_emails(self):
        raw = "User john.doe@example.com logged in"
        result = masking_agent.process(raw)
        assert "john.doe@example.com" not in result["sanitized_data"]
        assert "[REDACTED_EMAIL]" in result["sanitized_data"]

    def test_masks_jwt_tokens(self):
        raw = "Token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123"
        result = masking_agent.process(raw)
        assert "eyJhbGci" not in result["sanitized_data"]
        assert "[REDACTED_JWT_TOKEN]" in result["sanitized_data"]

    def test_masks_nested_json(self):
        raw = {
            "user": "admin@company.com",
            "server": "10.0.0.50",
            "auth": {"token": "Bearer abc123xyz"},
            "logs": ["Error from 192.168.1.1", "Request OK"],
        }
        result = masking_agent.process(raw)
        sanitized = result["sanitized_data"]
        
        assert "admin@company.com" not in str(sanitized)
        assert "10.0.0.50" not in str(sanitized)
        assert "192.168.1.1" not in str(sanitized)
        assert result["entities_scrubbed"] >= 3
        assert result["leakage_detected"] is False

    def test_handles_empty_input(self):
        result = masking_agent.process("")
        assert result["sanitized_data"] == ""
        assert result["status"] == "SUCCESS_ZERO_LEAKAGE"

    def test_preserves_non_sensitive_data(self):
        raw = "CPU usage at 85%, memory 4GB, service healthy"
        result = masking_agent.process(raw)
        assert result["sanitized_data"] == raw
        assert result["entities_scrubbed"] == 0

    def test_multiple_entities_in_single_text(self):
        raw = "User admin@test.com from 192.168.1.1 with Bearer token123 called api"
        result = masking_agent.process(raw)
        assert result["entities_scrubbed"] >= 3
        assert "admin@test.com" not in result["sanitized_data"]
        assert "192.168.1.1" not in result["sanitized_data"]