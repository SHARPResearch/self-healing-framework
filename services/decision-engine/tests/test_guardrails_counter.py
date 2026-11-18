# services/decision-engine/tests/test_guardrails_counter.py
from __future__ import annotations

import pytest

from app.decision.guardrails import action_counter


class FakePg:
    def __init__(self, count=0):
        self._count = count

    async def count_recent_actions(self, service_id, window_min=60):
        return self._count


@pytest.fixture
def patch_pg(monkeypatch):
    def _set(count):
        import app.persistence.postgres as pg
        monkeypatch.setattr(pg, "postgres_store", FakePg(count))
    return _set


@pytest.mark.asyncio
async def test_below_cap_allows(patch_pg):
    patch_pg(1)
    c = await action_counter.check("auth-service", {"max_per_hour": 3})
    assert c.blocked is False
    assert "1/3" in c.reason


@pytest.mark.asyncio
async def test_at_cap_blocks(patch_pg):
    patch_pg(3)
    c = await action_counter.check("auth-service", {"max_per_hour": 3})
    assert c.blocked is True


@pytest.mark.asyncio
async def test_db_error_fails_open(patch_pg, monkeypatch):
    class Boom:
        async def count_recent_actions(self, *a, **k):
            raise RuntimeError("db down")
    import app.persistence.postgres as pg
    monkeypatch.setattr(pg, "postgres_store", Boom())
    c = await action_counter.check("auth-service", {"max_per_hour": 3})
    assert c.blocked is False
    assert "fail-open" in c.reason