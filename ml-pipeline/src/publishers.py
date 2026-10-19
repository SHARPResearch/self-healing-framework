"""
publishers.py — Component 2: fan-out of lifecycle events to the rest of the system.

Doc1 §3: scored events go to the Redis Stream "anomaly_events" (consumed by the .NET Decision
Engine) and the Pub/Sub channel "ws:anomaly_broadcast" (pushed to every dashboard WebSocket).
Lifecycle transitions (drift alert, promotion, rollback) are published to the Pub/Sub channel
with type="model_lifecycle" so the dashboard and LLM Copilot see every adaptation as it happens.

The standalone pipeline defaults to NullPublisher; RedisPublisher needs `pip install redis` and a
reachable server, and is what services/ml-backend wires in after the lift.
"""

import json
import logging
from typing import Protocol

logger = logging.getLogger(__name__)

ANOMALY_STREAM = "anomaly_events"
BROADCAST_CHANNEL = "ws:anomaly_broadcast"


class EventPublisher(Protocol):
    def publish_lifecycle(self, payload: dict) -> None: ...


class NullPublisher:
    def publish_lifecycle(self, payload: dict) -> None:
        pass


class RecordingPublisher:
    """Keeps every payload in memory; used by tests and the offline evaluation."""

    def __init__(self):
        self.payloads: list[dict] = []

    def publish_lifecycle(self, payload: dict) -> None:
        self.payloads.append(payload)


class RedisPublisher:
    def __init__(self, url: str = "redis://localhost:6379"):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("RedisPublisher needs the `redis` package") from exc
        self._redis = redis.Redis.from_url(url)

    def publish_lifecycle(self, payload: dict) -> None:
        message = json.dumps({"type": "model_lifecycle", **payload}, default=str)
        self._redis.publish(BROADCAST_CHANNEL, message)
        self._redis.xadd(ANOMALY_STREAM, {"type": "model_lifecycle", "payload": message})
