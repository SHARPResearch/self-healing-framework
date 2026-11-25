"""
Tenant isolation in the database (docs/adr/0015): two tenants' stores share one PostgreSQL pool and
must never read each other's rows. Needs a database, so it only runs with TEST_DATABASE_URL set,
for example the local stack:

    TEST_DATABASE_URL=postgresql://postgres:selfheal@localhost:5433/selfheal uv run pytest tests/test_store_tenancy.py
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest

from app.store import PgStore

DSN = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="needs TEST_DATABASE_URL")


def test_two_tenants_on_one_pool_see_only_their_own_rows():
    async def scenario():
        a = PgStore(DSN, f"tenant-a-{uuid.uuid4().hex[:8]}")
        assert await a.start()
        b = a.for_tenant(f"tenant-b-{uuid.uuid4().hex[:8]}")
        try:
            now = datetime.now(timezone.utc)
            for store, msg in ((a, "a's alarm"), (b, "b's alarm")):
                await store.write_logs([{"id": uuid.uuid4().hex, "time": now, "service": "cartservice",
                                         "service_id": "cartservice", "source": "lifecycle",
                                         "level": "warn", "message": msg, "attrs": {}}])
                await store.save_checkpoint({"service_id": "cartservice", "source": "s", "step": 1,
                                             "production_version": 1, "blob": msg.encode()})
                await store.write_decision({"service_id": "cartservice", "action": "hold", "verdict": "incident"})
            a.logs.clear(), b.logs.clear()           # read from the database, not the cache
            assert [ln["message"] for ln in await a.query_logs()] == ["a's alarm"]
            assert [ln["message"] for ln in await b.query_logs()] == ["b's alarm"]
            assert (await a.load_checkpoints())["cartservice"]["blob"] == b"a's alarm"
            assert (await b.load_checkpoints())["cartservice"]["blob"] == b"b's alarm"
            assert (await a.counts())["lifecycle_decisions"] == 1
            await a.clear_checkpoints()
            assert await a.load_checkpoints() == {} and await b.load_checkpoints()
        finally:
            async with a.pool.acquire() as conn:
                for table in ("service_logs", "model_checkpoints", "lifecycle_decisions"):
                    await conn.execute(f"DELETE FROM {table} WHERE tenant_id = ANY($1)", [a.tenant, b.tenant])
            await b.stop()                           # does not close the shared pool
            await a.stop()

    asyncio.run(scenario())
