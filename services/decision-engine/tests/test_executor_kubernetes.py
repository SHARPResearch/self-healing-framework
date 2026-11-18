# services/decision-engine/tests/test_executor_kubernetes.py
"""
Tests for KubernetesExecutor using a mocked kubernetes client.
No cluster required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.decision.executor import ExecutionStatus
from app.decision.models import (
    Decision, PolicyOutcome, SeverityBreakdown,
)
from app.rules.models import ActionType, RiskLevel, RuleGuardrail


def _decision(action: ActionType, params: dict | None = None) -> Decision:
    return Decision(
        decision_id="DEC-1",
        anomaly_id="ANM-1",
        service_id="auth-service",
        rule_id="r",
        rule_version=1,
        action=action,
        action_params=params or {},
        detection_conf=0.9, rule_conf=0.9, final_conf=0.9,
        severity=SeverityBreakdown(
            base_severity=0.9, centrality=1.5, blast_factor=1.2,
            effective_severity=1.62, normalized=0.6, label="HIGH",
        ),
        base_risk=RiskLevel.LOW, blast_factor=1.2, centrality=1.5,
        guardrails=RuleGuardrail(),
        selection={"selected": {"rule_id": "r"}, "rejected": [],
                   "strategy": "priority_then_confidence", "reason": ""},
        policy_outcome=PolicyOutcome.AUTO_EXECUTE,
    )


@pytest.fixture
def patched_loader(monkeypatch):
    """Bypass the real kubeconfig load."""
    from app.decision import executor_kubernetes as ekm
    monkeypatch.setattr(ekm.KubernetesExecutor, "_load", lambda self: setattr(self, "_core_api", MagicMock()) or setattr(self, "_apps_api", MagicMock()) or setattr(self, "_custom_api", MagicMock()))


@pytest.mark.asyncio
async def test_restart_pod_calls_delete(patched_loader):
    from app.decision.executor_kubernetes import KubernetesExecutor
    ex = KubernetesExecutor()
    ex._core_api.list_namespaced_pod.return_value = MagicMock(
        items=[MagicMock(metadata=MagicMock(name="auth-service-abc"))]
    )
    result = await ex.execute(_decision(ActionType.RESTART_POD))
    assert result.status == ExecutionStatus.SUCCESS
    assert ex._core_api.delete_namespaced_pod.called
    assert "restarted 1 pod" in result.message


@pytest.mark.asyncio
async def test_scale_up_patches_deployment(patched_loader):
    from app.decision.executor_kubernetes import KubernetesExecutor
    ex = KubernetesExecutor()
    deploy = MagicMock()
    deploy.spec.replicas = 2
    ex._apps_api.read_namespaced_deployment.return_value = deploy
    result = await ex.execute(_decision(ActionType.SCALE_UP, {"replicas": 1}))
    assert result.status == ExecutionStatus.SUCCESS
    assert result.detail["from"] == 2
    assert result.detail["to"] == 3


@pytest.mark.asyncio
async def test_unknown_action_caught(patched_loader):
    """A handler exception becomes FAILED, not raised."""
    from app.decision.executor_kubernetes import KubernetesExecutor
    ex = KubernetesExecutor()
    ex._apps_api.read_namespaced_deployment.side_effect = RuntimeError("boom")
    result = await ex.execute(_decision(ActionType.SCALE_UP))
    assert result.status == ExecutionStatus.FAILED
    assert "boom" in result.message


@pytest.mark.asyncio
async def test_noop_succeeds(patched_loader):
    from app.decision.executor_kubernetes import KubernetesExecutor
    ex = KubernetesExecutor()
    result = await ex.execute(_decision(ActionType.NOOP))
    assert result.status == ExecutionStatus.SUCCESS