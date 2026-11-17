# services/decision-engine/tests/test_executor.py
"""
Tests for app.decision.executor.
"""
from __future__ import annotations

import pytest

from app.decision.executor import (
    ExecutionStatus,
    NoopExecutor,
)
from app.decision.models import (
    Decision,
    PolicyOutcome,
    SeverityBreakdown,
)
from app.rules.models import ActionType, RiskLevel, RuleGuardrail


def _decision() -> Decision:
    return Decision(
        decision_id="DEC-20260101-000000-abc123",
        anomaly_id="ANM-x",
        service_id="auth-service",
        rule_id="restart_pod_high_cpu",
        rule_version=1,
        action=ActionType.RESTART_POD,
        action_params={"grace_period_sec": 30},
        detection_conf=0.92,
        rule_conf=0.85,
        final_conf=0.89,
        severity=SeverityBreakdown(
            base_severity=0.9, centrality=1.5, blast_factor=1.2,
            effective_severity=1.62, normalized=0.6, label="HIGH",
        ),
        base_risk=RiskLevel.MEDIUM,
        blast_factor=1.2,
        centrality=1.5,
        guardrails=RuleGuardrail(),
        selection={
            "selected": {"rule_id": "restart_pod_high_cpu"},
            "rejected": [],
            "strategy": "priority_then_confidence",
            "reason": "test",
        },
        policy_outcome=PolicyOutcome.AUTO_EXECUTE,
    )


@pytest.mark.asyncio
async def test_noop_executor_returns_not_implemented():
    ex = NoopExecutor()
    result = await ex.execute(_decision())

    assert result.status == ExecutionStatus.NOT_IMPLEMENTED
    assert result.decision_id.startswith("DEC-")
    assert result.service_id == "auth-service"
    assert result.action == ActionType.RESTART_POD
    assert "No Kubernetes" in result.message
    assert result.detail["policy_outcome"] == "AUTO_EXECUTE"


@pytest.mark.asyncio
async def test_noop_executor_does_not_raise_on_null_policy():
    d = _decision()
    d.policy_outcome = None
    ex = NoopExecutor()
    result = await ex.execute(d)
    assert result.status == ExecutionStatus.NOT_IMPLEMENTED
    assert result.detail["policy_outcome"] is None