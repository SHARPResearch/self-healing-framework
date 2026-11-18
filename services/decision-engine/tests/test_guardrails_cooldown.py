# services/decision-engine/tests/test_guardrails_cooldown.py
from __future__ import annotations

import pytest

from app.decision.guardrails import cooldown
from app.decision.guardrails.store import InMemoryStore, reset_store, set_store


class FakePg:
    def __init__(self):
        self._active = {}

    async def get_active_cooldown(self, service_id):
        return self._active.get(service_id)

    async def upsert_cooldown(self, service_id, decision_id, expires_at):
        self._active[service_id] = {
            "service_id": service_id,
            "decision_id": decision_id,
            "started_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            "expires_at": expires_at,
        }
        return True


@pytest.fixture
def fake_pg(monkeypatch):
    import app.persistence.postgres as pg
    fake = FakePg()
    monkeypatch.setattr(pg, "postgres_store", fake)
    set_store(InMemoryStore())
    yield fake
    reset_store()


@pytest.mark.asyncio
async def test_no_cooldown_initially(fake_pg):
    c = await cooldown.check("auth-service", {"cooldown_seconds": 300})
    assert c.blocked is False


@pytest.mark.asyncio
async def test_mark_then_check_blocks(fake_pg):
    await cooldown.mark("auth-service", "DEC-1", {"cooldown_seconds": 300})
    c = await cooldown.check("auth-service", {"cooldown_seconds": 300})
    assert c.blocked is True
    assert "acted on within" in c.reason


@pytest.mark.asyncio
async def test_zero_window_never_blocks(fake_pg):
    await cooldown.mark("auth-service", "DEC-1", {"cooldown_seconds": 0})
    c = await cooldown.check("auth-service", {"cooldown_seconds": 0})
    assert c.blocked is False
    
@pytest.mark.asyncio
async def test_zero_window_never_marks(fake_pg):
    """A zero window must not write anything to Postgres."""
    await cooldown.mark("auth-service", "DEC-1", {"cooldown_seconds": 0})
    assert await fake_pg.get_active_cooldown("auth-service") is None


@pytest.mark.asyncio
async def test_missing_guardrails_uses_default(fake_pg):
    """No cooldown_seconds key → default 300s applies."""
    await cooldown.mark("auth-service", "DEC-1", None)
    c = await cooldown.check("auth-service", None)
    assert c.blocked is True
    assert c.detail["window_sec"] == 300