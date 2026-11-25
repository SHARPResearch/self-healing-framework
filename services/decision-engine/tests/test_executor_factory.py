from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.decision.executor import (
    AuthRequiredExecutor,
    ExecutionStatus,
    NoopExecutor,
    get_executor,
    kubernetes_auth_configured,
)
from app.rules.models import ActionType


@pytest.fixture(autouse=True)
def clear_kubernetes_auth(monkeypatch):
    monkeypatch.setattr(settings, "KUBERNETES_DRY_RUN", True)
    monkeypatch.setattr(settings, "KUBERNETES_KUBECONFIG_PATH", "")
    monkeypatch.setattr(settings, "KUBERNETES_API_SERVER", "")
    monkeypatch.setattr(settings, "KUBERNETES_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "KUBERNETES_IN_CLUSTER", False)
    monkeypatch.setattr(settings, "KUBERNETES_ALLOW_IN_CLUSTER", False)


def test_factory_returns_noop_when_dry_run():
    assert isinstance(get_executor(), NoopExecutor)


def test_factory_blocks_when_no_auth_is_supplied(monkeypatch):
    monkeypatch.setattr(settings, "KUBERNETES_DRY_RUN", False)

    assert not kubernetes_auth_configured()
    assert isinstance(get_executor(), AuthRequiredExecutor)


@pytest.mark.asyncio
async def test_auth_required_executor_skips_decision():
    decision = MagicMock(
        decision_id="DEC-1",
        service_id="cartservice",
        action=ActionType.RESTART_POD,
        action_params={},
        policy_outcome=None,
    )

    result = await AuthRequiredExecutor().execute(decision)

    assert result.status == ExecutionStatus.SKIPPED
    assert result.detail["reason"] == "KUBERNETES_AUTH_REQUIRED"


def test_factory_accepts_explicit_kubeconfig(monkeypatch):
    monkeypatch.setattr(settings, "KUBERNETES_DRY_RUN", False)
    monkeypatch.setattr(settings, "KUBERNETES_KUBECONFIG_PATH", "C:/tmp/kubeconfig")

    assert kubernetes_auth_configured()


def test_factory_accepts_server_and_token(monkeypatch):
    monkeypatch.setattr(settings, "KUBERNETES_DRY_RUN", False)
    monkeypatch.setattr(settings, "KUBERNETES_API_SERVER", "https://127.0.0.1:6443")
    monkeypatch.setattr(settings, "KUBERNETES_AUTH_TOKEN", "token")

    assert kubernetes_auth_configured()


def test_factory_blocks_when_in_cluster_not_explicitly_allowed(monkeypatch):
    monkeypatch.setattr(settings, "KUBERNETES_DRY_RUN", False)
    monkeypatch.setattr(settings, "KUBERNETES_IN_CLUSTER", True)

    assert not kubernetes_auth_configured()


def test_factory_falls_back_to_blocked_when_import_fails(monkeypatch):
    import sys

    monkeypatch.setattr(settings, "KUBERNETES_KUBECONFIG_PATH", "C:/tmp/kubeconfig")
    monkeypatch.setattr(settings, "KUBERNETES_DRY_RUN", False)
    monkeypatch.setitem(sys.modules, "app.decision.executor_kubernetes", None)

    assert isinstance(get_executor(), AuthRequiredExecutor)
