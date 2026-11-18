# services/decision-engine/tests/test_guardrails_store.py
from __future__ import annotations

import asyncio

import pytest

from app.decision.guardrails.store import InMemoryStore, reset_store, set_store


@pytest.fixture(autouse=True)
def clean_store():
    store = InMemoryStore()
    set_store(store)
    yield store
    reset_store()


@pytest.mark.asyncio
async def test_set_and_get(clean_store):
    await clean_store.set("k", "v")
    assert await clean_store.get("k") == "v"


@pytest.mark.asyncio
async def test_ttl_expires(clean_store):
    await clean_store.set("k", "v", ttl_sec=1)
    assert await clean_store.get("k") == "v"
    await asyncio.sleep(1.1)
    assert await clean_store.get("k") is None


@pytest.mark.asyncio
async def test_incr(clean_store):
    assert await clean_store.incr("counter") == 1
    assert await clean_store.incr("counter") == 2
    assert await clean_store.incr("counter") == 3


@pytest.mark.asyncio
async def test_exists(clean_store):
    assert await clean_store.exists("nope") is False
    await clean_store.set("yep", "1")
    assert await clean_store.exists("yep") is True


@pytest.mark.asyncio
async def test_delete(clean_store):
    await clean_store.set("k", "v")
    await clean_store.delete("k")
    assert await clean_store.get("k") is None