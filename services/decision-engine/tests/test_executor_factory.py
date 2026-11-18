# services/decision-engine/tests/test_executor_factory.py
from __future__ import annotations

import pytest

from app.decision import executor as exec_mod
from app.decision.executor import NoopExecutor, get_executor


def test_factory_returns_noop_when_dry_run(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "KUBERNETES_DRY_RUN", True)
    ex = get_executor()
    assert isinstance(ex, NoopExecutor)


def test_factory_falls_back_to_noop_on_import_error(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "KUBERNETES_DRY_RUN", False)

    # Make KubernetesExecutor import blow up
    import sys
    monkeypatch.setitem(sys.modules, "app.decision.executor_kubernetes", None)

    ex = get_executor()
    assert isinstance(ex, NoopExecutor)