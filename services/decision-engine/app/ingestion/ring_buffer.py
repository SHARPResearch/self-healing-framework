"""
In-memory rolling buffer of the last N seconds of telemetry per service.
When an anomaly fires, we slice this to build the snapshot window.
"""
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from app.config import settings


class TelemetryRingBuffer:
    def __init__(self, retention_seconds: int = None):
        self.retention = timedelta(
            seconds=retention_seconds or settings.RING_BUFFER_RETENTION_SEC
        )
        self.infra: dict[str, deque] = {}
        self.app: dict[str, deque] = {}
        self._lock = Lock()

    def push_infra(self, service_id: str, timestamp: datetime, data: dict):
        with self._lock:
            buf = self.infra.setdefault(service_id, deque())
            buf.append({"time": timestamp, "data": data})
            self._trim(buf)

    def push_app(self, service_id: str, timestamp: datetime, data: dict):
        with self._lock:
            buf = self.app.setdefault(service_id, deque())
            buf.append({"time": timestamp, "data": data})
            self._trim(buf)

    def slice_infra(self, service_id: str, start: datetime, end: datetime) -> list[dict]:
        with self._lock:
            return [
                x for x in self.infra.get(service_id, [])
                if start <= x["time"] <= end
            ]

    def slice_app(self, service_id: str, start: datetime, end: datetime) -> list[dict]:
        with self._lock:
            return [
                x for x in self.app.get(service_id, [])
                if start <= x["time"] <= end
            ]

    def stats(self) -> dict:
        with self._lock:
            return {
                "services_infra": len(self.infra),
                "services_app": len(self.app),
                "total_infra_points": sum(len(b) for b in self.infra.values()),
                "total_app_points": sum(len(b) for b in self.app.values()),
            }

    def _trim(self, buf: deque):
        cutoff = datetime.now(timezone.utc) - self.retention
        while buf and buf[0]["time"] < cutoff:
            buf.popleft()


ring_buffer = TelemetryRingBuffer()