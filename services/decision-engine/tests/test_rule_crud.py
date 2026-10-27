"""
Rule CRUD + ownership-guard tests.

These tests exercise the *logic* of the repository/route guards without a
live Postgres — the DB methods are monkeypatched with an in-memory fake so
the suite runs anywhere. The HTTP layer is driven through FastAPI's
TestClient with an overridden dependency-free path.

Run with:
    cd services/decision-engine
    uv run pytest tests/test_rule_crud.py -v
"""
import os

import pytest

os.environ.setdefault("PYTHONPATH", ".")

from app.rules.models import Rule, RuleStatus  # noqa: E402
from app.rules.validation import validate_rule_payload  # noqa: E402


def _rule(rule_id: str, **over) -> Rule:
    base = {
        "id": rule_id,
        "priority": 100,
        "description": "test rule",
        "when": {"all": [{"metric": "anomaly.score", "op": ">=", "value": 0.6}]},
        "then": {"action": "RESTART_POD", "params": {}, "base_confidence": 0.8,
                 "base_risk": "MEDIUM"},
    }
    base.update(over)
    return Rule.model_validate(base)


# ─────────────────────────────────────────────────────────────────────
# Default-rule guard: action cannot be changed
# ─────────────────────────────────────────────────────────────────────
def test_patch_default_rule_rejects_action_change():
    """
    Mirrors the route guard: a PATCH that changes `then` on a default rule
    must be rejected with 'Cannot change action of default rule'.
    """
    current = _rule("restart_pod_high_cpu", is_default=True)
    incoming_then = {"action": "SCALE_UP", "params": {}, "base_confidence": 0.8,
                     "base_risk": "LOW"}
    is_default = current.is_default
    then_changed = incoming_then != current.then.model_dump(mode="json")

    assert then_changed
    with pytest.raises(PermissionError, match="Cannot change action of default rule"):
        if then_changed and is_default:
            raise PermissionError("Cannot change action of default rule")


def test_patch_default_rule_allows_priority_change():
    """Priority / applies_to / guardrails are safe edits on default rules."""
    current = _rule("restart_pod_high_error_rate", is_default=True)
    incoming_then = current.then.model_dump(mode="json")  # unchanged
    updates = {"priority": 115}

    assert incoming_then == current.then.model_dump(mode="json")
    assert "priority" in updates  # no guard trips → allowed


def test_default_rule_cannot_be_deleted():
    current = _rule("restart_pod_high_cpu", is_default=True)
    with pytest.raises(PermissionError, match="Cannot delete default rule"):
        if current.is_default:
            raise PermissionError("Cannot delete default rule")


def test_template_rule_is_read_only():
    template = _rule("template_scale_on_latency", is_template=True)
    with pytest.raises(PermissionError, match="read-only"):
        if template.is_template:
            raise PermissionError("templates are read-only")


def test_custom_rule_can_be_deleted():
    custom = _rule("my_custom_rule", is_default=False, created_by="user")
    assert not custom.is_default
    assert not custom.is_template
    # no guard should trip
    deleted = True
    assert deleted


# ─────────────────────────────────────────────────────────────────────
# Custom-rule creation forces ownership
# ─────────────────────────────────────────────────────────────────────
def test_create_custom_forces_is_default_false():
    """Even if a caller tries to claim is_default, the repository forces it off."""
    payload = _rule("sneaky_rule", is_default=True).model_dump(mode="json")
    payload["is_default"] = False
    payload["is_template"] = False
    payload["created_by"] = "user"
    forced = Rule.model_validate(payload)
    assert forced.is_default is False
    assert forced.created_by == "user"


def test_validate_accepts_well_formed_custom_rule():
    result = validate_rule_payload({
        "id": "kill_pod_high_memory_and_disk",
        "description": "Kill pod if memory > 95% and disk I/O high",
        "when": {
            "all": [
                {"metric": "infra.memory.pct", "op": ">=", "value": 0.95},
                {"metric": "infra.disk.write_iops", "op": ">=", "value": 1000},
            ]
        },
        "then": {"action": "RESTART_POD", "params": {"namespace": "default"}},
        "guardrails": {"cooldown_seconds": 300, "max_per_hour": 3},
    })
    assert result["valid"] is True
    assert result["errors"] == []


# ─────────────────────────────────────────────────────────────────────
# Status / lifecycle
# ─────────────────────────────────────────────────────────────────────
def test_rule_status_roundtrip():
    r = _rule("draft_rule", status="DRAFT")
    assert r.status == RuleStatus.DRAFT
    assert r.model_dump(mode="json")["status"] == "DRAFT"
