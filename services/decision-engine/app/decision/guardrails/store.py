# services/decision-engine/app/decision/guardrails/store.py
"""
Key/value store used by the guardrails.

Two backends:
    * RedisStore     — production, when REDIS_URL is set and reachable
    * InMemoryStore  — fallback, single-process, loses state on restart

The Postgres layer (see persistence/schemas.py) is the *source of truth*
for anything that must survive restarts (idempotency keys, cooldowns).
Redis is a cache front. If both are unavailable, guardrails fail-open:
they allow the decision and log a warning. This is deliberate — blocking
every decision because Redis is down would be worse than a slightly
sloppy cooldown during an outage.

API (both backends):
    async def get(key: str) -> str | None
    async def set(key: str, value: str, ttl_sec: int | None = None) -> None
    async def delete(key: str) -> None
    async def incr(key: str, ttl_sec: int | None = None) -> int
    async def exists(key: str) -> bool
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Protocol, runtime_checkable

from app.config import settings

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Protocol
# ─────────────────────────────────────────────────────────────────────
@runtime_checkable
class KeyValueStore(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_sec: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def incr(self, key: str, ttl_sec: int | None = None) -> int: ...
    async def exists(self, key: str) -> bool: ...


# ─────────────────────────────────────────────────────────────────────
# In-memory backend (single-process, dev/test)
# ─────────────────────────────────────────────────────────────────────
class InMemoryStore:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}
        self._lock = asyncio.Lock()

    def _alive(self, key: str) -> bool:
        item = self._data.get(key)
        if item is None:
            return False
        _, expiry = item
        if expiry is not None and expiry < time.monotonic():
            self._data.pop(key, None)
            return False
        return True

    async def get(self, key: str) -> str | None:
        async with self._lock:
            if not self._alive(key):
                return None
            return self._data[key][0]

    async def set(self, key: str, value: str, ttl_sec: int | None = None) -> None:
        async with self._lock:
            expiry = time.monotonic() + ttl_sec if ttl_sec else None
            self._data[key] = (str(value), expiry)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    async def incr(self, key: str, ttl_sec: int | None = None) -> int:
        async with self._lock:
            if not self._alive(key):
                expiry = time.monotonic() + ttl_sec if ttl_sec else None
                self._data[key] = ("1", expiry)
                return 1
            current = int(self._data[key][0]) + 1
            expiry = self._data[key][1]
            self._data[key] = (str(current), expiry)
            return current

    async def exists(self, key: str) -> bool:
        async with self._lock:
            return self._alive(key)

    def clear(self) -> None:
        """Test helper."""
        self._data.clear()


# ─────────────────────────────────────────────────────────────────────
# Redis backend
# ─────────────────────────────────────────────────────────────────────
class RedisStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        val = await self._client.get(key)
        return val.decode() if isinstance(val, bytes) else val

    async def set(self, key: str, value: str, ttl_sec: int | None = None) -> None:
        if ttl_sec:
            await self._client.setex(key, ttl_sec, value)
        else:
            await self._client.set(key, value)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def incr(self, key: str, ttl_sec: int | None = None) -> int:
        n = await self._client.incr(key)
        if n == 1 and ttl_sec:
            await self._client.expire(key, ttl_sec)
        return int(n)

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))


# ─────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────
_store: KeyValueStore | None = None


def _try_redis() -> KeyValueStore | None:
    url = getattr(settings, "REDIS_URL", "") or ""
    if not url:
        return None
    try:
        import redis.asyncio as aioredis  # type: ignore
    except ImportError:
        log.warning("redis package not installed; falling back to in-memory store")
        return None
    try:
        client = aioredis.from_url(url, decode_responses=False)
        log.info("Guardrails using Redis backend (%s)", url.split("@")[-1])
        return RedisStore(client)
    except Exception:
        log.exception("Failed to connect Redis at %s; falling back to in-memory", url)
        return None


def get_store() -> KeyValueStore:
    """
    Return the process-wide singleton store. Prefers Redis, falls back to
    in-memory. Tests can override via `set_store(...)`.
    """
    global _store
    if _store is None:
        _store = _try_redis() or InMemoryStore()
        if isinstance(_store, InMemoryStore):
            log.info("Guardrails using in-memory store (dev/test)")
    return _store


def set_store(store: KeyValueStore | None) -> None:
    """Test helper — override the singleton."""
    global _store
    _store = store


def reset_store() -> None:
    """Test helper — drop the current store."""
    global _store
    _store = None