# services/decision-engine/tests/test_guardrails_idempotency.py
from __future__ import annotations

import pytest

from app.decision.action_selector import RecoveryAction
from app.decision.blast_analysis import BlastRadiusAnalysis
from app.decision.guardrails import idempotency
from app.decision.guardrails.store import InMemoryStore, reset_store, set_store
from app.rules.models import ActionType, RiskLevel


class FakePg:
    def __init__(self):
        self._keys = {}

    async def get_idempotency_key(self, key):
        return self._keys.get(key)

    async def save_idempotency_key(self, key, decision_id, expires_at):
        self._keys[key] = {"key": key, "decision_id": decision_id, "expires_at": expires_at}
        return True


@pytest.fixture
def fake_pg(monkeypatch):
    import app.persistence.postgres as pg
    fake = FakePg()
    monkeypatch.setattr(pg, "postgres_store", fake)
    set_store(InMemoryStore())
    yield fake
    reset_store()


def _ra(guardrails=None) -> RecoveryAction:
    return RecoveryAction(
        rule_id="r", rule_version=1, action=ActionType.RESTART_POD,
        params={}, service_id="auth-service", confidence=0.9,
        base_risk=RiskLevel.LOW,
        blast=BlastRadiusAnalysis(
            service_id="auth-service", action=ActionType.RESTART_POD,
            size=0, factor=1.0, weighted=0.0,
            recommended_risk=RiskLevel.LOW,
        ),
        guardrails=guardrails or {},
    )


@pytest.mark.asyncio
async def test_first_time_allows(fake_pg):
    c = await idempotency.check(_ra(), "ANM-1")
    assert c.blocked is False


@pytest.mark.asyncio
async def test_after_mark_blocks(fake_pg):
    await idempotency.mark(_ra(), "ANM-1", "DEC-1")
    c = await idempotency.check(_ra(), "ANM-1")
    assert c.blocked is True
    assert "already executed" in c.reason


@pytest.mark.asyncio
async def test_custom_template(fake_pg):
    g = {"idempotency_key": "custom:{{service.id}}:{{action}}"}
    await idempotency.mark(_ra(g), "ANM-1", "DEC-1")
    c = await idempotency.check(_ra(g), "ANM-1")
    assert c.blocked is True
    assert "custom:auth-service:RESTART_POD" in c.reason