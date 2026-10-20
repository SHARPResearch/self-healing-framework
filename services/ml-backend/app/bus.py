"""
bus.py — event fan-out to WebSocket clients and to Redis (Doc1 §3).

Every message is published to the Redis Pub/Sub channel `ws:anomaly_broadcast` (every replica's
WebSocket gateway subscribes to it, so a client sees events from all replicas) and appended to the
Redis Stream `anomaly_events` (consumed by the .NET Decision Engine with XREADGROUP). Message
envelope, also the WebSocket contract (services/ml-backend/README.md):

    {"type": <message type>, "service_id": <id or null>, "ts": <ISO 8601>, "data": {...}}

If Redis is unreachable, messages fan out in process instead so a single backend still serves its
own WebSocket clients.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

BROADCAST_CHANNEL = "ws:anomaly_broadcast"
ANOMALY_STREAM = "anomaly_events"
STREAM_MAXLEN = 20000


def envelope(msg_type: str, service_id: Optional[str], data: dict) -> dict:
    return {"type": msg_type, "service_id": service_id,
            "ts": datetime.now(timezone.utc).isoformat(), "data": data}


class Bus:
    def __init__(self):
        self.redis = None
        self._local: set[asyncio.Queue] = set()

    async def start(self, redis_url: Optional[str]) -> bool:
        if not redis_url:
            return False
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(redis_url, decode_responses=True)
            await asyncio.wait_for(client.ping(), timeout=2)
            self.redis = client
            logger.info("bus: Redis connected at %s", redis_url)
            return True
        except Exception as exc:  # noqa: BLE001 - any failure means fall back
            logger.warning("bus: Redis unavailable (%s), using in-process fan-out", exc)
            self.redis = None
            return False

    async def stop(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()

    @property
    def redis_ok(self) -> bool:
        return self.redis is not None

    async def publish(self, message: dict) -> None:
        if self.redis is not None:
            data = json.dumps(message, default=str)
            try:
                await self.redis.publish(BROADCAST_CHANNEL, data)
                if message["type"] != "log":      # log lines are for the UI, not the Decision Engine
                    await self.redis.xadd(ANOMALY_STREAM, {"type": message["type"], "payload": data},
                                          maxlen=STREAM_MAXLEN, approximate=True)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("bus: Redis publish failed (%s), switching to in-process fan-out", exc)
                self.redis = None
        for q in list(self._local):
            if q.qsize() < 1000:      # a slow client must not grow memory without bound
                q.put_nowait(message)

    async def subscribe(self) -> AsyncIterator[dict]:
        if self.redis is not None:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(BROADCAST_CHANNEL)
            try:
                async for raw in pubsub.listen():
                    if raw.get("type") == "message":
                        yield json.loads(raw["data"])
            finally:
                await pubsub.unsubscribe(BROADCAST_CHANNEL)
                await pubsub.aclose()
        else:
            q: asyncio.Queue = asyncio.Queue()
            self._local.add(q)
            try:
                while True:
                    yield await q.get()
            finally:
                self._local.discard(q)
