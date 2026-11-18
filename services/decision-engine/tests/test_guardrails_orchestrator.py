# services/decision-engine/tests/test_guardrails_orchestrator.py
from __future__ import annotations

import pytest

from app.decision.action_selector import RecoveryAction
from app.decision.blast_analysis import BlastRadiusAnalysis
from app.decision.guardrails import check, mark
from app.decision.guardrails.store import InMemoryStore, reset_store, set_store
from app.rules.models import ActionType, RiskLevel


class FakePg:
    def __init__(self):
        self._cooldowns = {}
        self._idem = {}
        self._action_count = 0

    async def get_active_cooldown(self, sid):
        return self._cooldowns.get(sid)

    async def upsert_cooldown(self, sid, decision_id, expires_at):
        from datetime import datetime, timezone
        self._cooldowns[sid] = {
            "service_id": sid, "decision_id": decision_id,
            "started_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
        }
        return True

    async def count_recent_actions(self, sid, window_min=60):
        return self._action_count

    async def get_idempotency_key(self, key):
        return self._idem.get(key)

    async def save_idempotency_key(self, key, decision_id, expires_at):
        self._idem[key] = {"key": key, "decision_id": decision_id, "expires_at": expires_at}
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
        guardrails=guardrails or {"cooldown_seconds": 300, "max_per_hour": 3},
    )


@pytest.mark.asyncio
async def test_all_pass(fake_pg):
    v = await check(_ra(), "ANM-1")
    assert v.allowed is True
    assert len(v.checks) == 3
    assert all(c.blocked is False for c in v.checks)


@pytest.mark.asyncio
async def test_cooldown_blocks_first(fake_pg):
    await mark(_ra(), "ANM-1", "DEC-1")
    v = await check(_ra(), "ANM-2")
    assert v.allowed is False
    assert v.blocker == "cooldown"


@pytest.mark.asyncio
async def test_counter_blocks_when_at_cap(fake_pg):
    fake_pg._action_count = 3
    v = await check(_ra(), "ANM-1")
    assert v.allowed is False
    assert v.blocker == "action_counter"


@pytest.mark.asyncio
async def test_idempotency_blocks_repeat(fake_pg):
    await mark(_ra(), "ANM-1", "DEC-1")
    # Clear the cooldown so idempotency is the first blocker that fires
    fake_pg._cooldowns.clear()
    from app.decision.guardrails.store import get_store
    await get_store().delete("cooldown:auth-service")

    v = await check(_ra(), "ANM-1")
    assert v.allowed is False
    assert v.blocker == "idempotency"