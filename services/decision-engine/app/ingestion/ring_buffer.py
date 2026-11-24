# services\decision-engine\app\ingestion\ring_buffer.py
"""
In-memory rolling buffer of the last N seconds of telemetry per service.
When an anomaly fires, we slice this to build the snapshot window.
"""
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from app.config import settings

def _as_utc(ts: datetime) -> datetime:
    """Force any datetime to timezone-aware UTC."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)  # assume naive=UTC
    return ts.astimezone(timezone.utc)


class TelemetryRingBuffer:
    def __init__(self, retention_seconds: int = None):
        self.retention = timedelta(
            seconds=retention_seconds or settings.RING_BUFFER_RETENTION_SEC
        )
        self.infra: dict[str, deque] = {}
        self.app: dict[str, deque] = {}
        self._lock = Lock()

    def push_infra(self, service_id, timestamp, data):
        with self._lock:
            buf = self.infra.setdefault(service_id, deque())
            buf.append({"time": _as_utc(timestamp), "data": data})
            self._trim(buf)

    def push_app(self, service_id, timestamp, data):
        with self._lock:
            buf = self.app.setdefault(service_id, deque())
            buf.append({"time": _as_utc(timestamp), "data": data})
            self._trim(buf)

    def slice_infra(self, service_id, start, end):
        start, end = _as_utc(start), _as_utc(end)
        with self._lock:
            return [x for x in self.infra.get(service_id, [])
                    if start <= x["time"] <= end]

    def slice_app(self, service_id, start, end):
        start, end = _as_utc(start), _as_utc(end)
        with self._lock:
            return [x for x in self.app.get(service_id, [])
                    if start <= x["time"] <= end]

    

    def stats(self) -> dict:
        with self._lock:
            return {
                "services_infra": len(self.infra),
                "services_app": len(self.app),
                "total_infra_points": sum(len(b) for b in self.infra.values()),
                "total_app_points": sum(len(b) for b in self.app.values()),
            }

    def _trim(self, buf):
        cutoff = datetime.now(timezone.utc) - self.retention
        while buf and _as_utc(buf[0]["time"]) < cutoff:
            buf.popleft()


ring_buffer = TelemetryRingBuffer()