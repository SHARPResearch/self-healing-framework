"""
Rule validation tests — validate_rule_payload() in app/rules/validation.py.

Run with:
    cd services/decision-engine
    uv run pytest tests/test_rule_validation.py -v
"""
import os

import pytest

os.environ.setdefault("PYTHONPATH", ".")

from app.rules.models import Rule  # noqa: E402
from app.rules.validation import (  # noqa: E402
    _iter_leaf_conditions,
    count_matches,
    validate_rule_payload,
)


def _base(**over):
    payload = {
        "id": "valid_rule",
        "description": "a rule",
        "when": {"all": [{"metric": "anomaly.score", "op": ">=", "value": 0.6}]},
        "then": {"action": "RESTART_POD", "params": {}},
    }
    payload.update(over)
    return payload


# ─────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────
def test_valid_rule_passes():
    result = validate_rule_payload(_base())
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["rule"]["id"] == "valid_rule"


def test_valid_rule_with_nested_any_in_all():
    payload = _base(when={
        "all": [
            {"metric": "anomaly.score", "op": ">=", "value": 0.5},
            {"any": [
                {"metric": "service.health", "op": "in", "value": ["degraded", "down"]},
                {"metric": "infra.cpu.usage_pct", "op": ">=", "value": 0.8},
            ]},
        ]
    })
    result = validate_rule_payload(payload)
    assert result["valid"] is True


# ─────────────────────────────────────────────────────────────────────
# id / slug
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad_id", ["has space", "UPPER!", "dot.notation", ""])
def test_bad_id_is_rejected(bad_id):
    result = validate_rule_payload(_base(id=bad_id))
    assert result["valid"] is False
    assert any("slug" in e or "id" in e for e in result["errors"])


def test_id_collision_is_an_error_when_creating():
    result = validate_rule_payload(
        _base(id="restart_pod_high_cpu"),
        existing_ids={"restart_pod_high_cpu"},
        is_update=False,
    )
    assert result["valid"] is False
    assert any("already exists" in e for e in result["errors"])


def test_id_collision_is_fine_when_updating():
    result = validate_rule_payload(
        _base(id="restart_pod_high_cpu"),
        existing_ids={"restart_pod_high_cpu"},
        is_update=True,
    )
    assert result["valid"] is True


# ─────────────────────────────────────────────────────────────────────
# applies_to
# ─────────────────────────────────────────────────────────────────────
def test_unknown_layer_is_rejected():
    result = validate_rule_payload(_base(applies_to={
        "layers": ["domain", "frontend"], "services": ["*"], "exclude_services": []
    }))
    assert result["valid"] is False
    assert any("unknown layers" in e for e in result["errors"])


def test_known_layers_pass():
    result = validate_rule_payload(_base(applies_to={
        "layers": ["edge", "bff", "domain", "data"],
        "services": ["*"],
        "exclude_services": [],
    }))
    assert result["valid"] is True


# ─────────────────────────────────────────────────────────────────────
# Condition tree
# ─────────────────────────────────────────────────────────────────────
def test_empty_and_group_is_rejected():
    result = validate_rule_payload(_base(when={"all": []}))
    assert result["valid"] is False
    assert any("at least one condition" in e for e in result["errors"])


def test_bad_operator_is_rejected():
    result = validate_rule_payload(_base(when={
        "all": [{"metric": "anomaly.score", "op": "~~", "value": 1}]
    }))
    assert result["valid"] is False


def test_in_operator_requires_list_value():
    result = validate_rule_payload(_base(when={
        "all": [{"metric": "anomaly.severity", "op": "in", "value": "high"}]
    }))
    assert result["valid"] is False
    assert any("must be a list" in e for e in result["errors"])


def test_leaf_missing_value_is_rejected():
    result = validate_rule_payload(_base(when={
        "all": [{"metric": "anomaly.score", "op": ">="}]
    }))
    assert result["valid"] is False
    # Pydantic catches the missing 'value' before the structural walker does,
    # so assert on either message shape.
    assert any(
        "missing a 'value'" in e or "value" in e for e in result["errors"]
    )


# ─────────────────────────────────────────────────────────────────────
# Action
# ─────────────────────────────────────────────────────────────────────
def test_invalid_action_is_rejected():
    result = validate_rule_payload(_base(then={"action": "EXPLODE", "params": {}}))
    assert result["valid"] is False


@pytest.mark.parametrize(
    "action",
    ["RESTART_POD", "SCALE_UP", "SCALE_DOWN", "ROLLBACK", "OPEN_CIRCUIT",
     "CLOSE_CIRCUIT", "FLUSH_CACHE", "INCREASE_DB_POOL", "SCALE_CONSUMERS",
     "DRAIN_NODE", "NOOP"],
)
def test_every_known_action_is_accepted(action):
    result = validate_rule_payload(_base(then={"action": action, "params": {}}))
    assert result["valid"] is True


# ─────────────────────────────────────────────────────────────────────
# Warnings (non-fatal)
# ─────────────────────────────────────────────────────────────────────
def test_unknown_metric_namespace_warns_but_still_valid():
    result = validate_rule_payload(_base(when={
        "all": [{"metric": "mystery.metric.here", "op": ">=", "value": 1}]
    }))
    assert result["valid"] is True
    assert any("unknown namespace" in w for w in result["warnings"])


def test_overlapping_services_and_exclusions_warn():
    result = validate_rule_payload(_base(applies_to={
        "layers": ["domain"],
        "services": ["auth-service"],
        "exclude_services": ["auth-service"],
    }))
    assert result["valid"] is True
    assert any("exclude_services" in w for w in result["warnings"])


# ─────────────────────────────────────────────────────────────────────
# Leaf extraction helper
# ─────────────────────────────────────────────────────────────────────
def test_iter_leaf_conditions_flattens_tree():
    leaves = _iter_leaf_conditions({
        "all": [
            {"metric": "a.b", "op": ">=", "value": 1},
            {"any": [
                {"metric": "c.d", "op": "<", "value": 2},
                {"metric": "e.f", "op": "==", "value": 3},
            ]},
        ]
    })
    assert [l.metric for l in leaves] == ["a.b", "c.d", "e.f"]


# ─────────────────────────────────────────────────────────────────────
# count_matches — dry run against contexts
# ─────────────────────────────────────────────────────────────────────
class _FakeCtx:
    def __init__(self, sid, layer, score):
        self.service = {"layer": layer, "service_id": sid}
        self.service_id = sid
        self.anomaly = {"id": f"ANM-{sid}", "anomaly_score": score}

    def resolve(self, path):
        if path == "anomaly.score":
            return self.anomaly["anomaly_score"]
        return None


def test_count_matches_respects_applies_to():
    rule = Rule.model_validate(_base(
        when={"all": [{"metric": "anomaly.score", "op": ">=", "value": 0.7}]},
        applies_to={"layers": ["domain"], "services": ["*"], "exclude_services": []},
    ))
    contexts = [
        _FakeCtx("auth-service", "domain", 0.9),   # eligible, matches
        _FakeCtx("api-gateway", "edge", 0.95),     # wrong layer → skipped
        _FakeCtx("orders-service", "domain", 0.4), # eligible, no match
    ]
    out = count_matches(rule, contexts)
    assert out["total_anomalies"] == 3
    assert out["eligible_anomalies"] == 2
    assert out["matched_count"] == 1
    assert "Would match 1 of 3" in out["message"]
