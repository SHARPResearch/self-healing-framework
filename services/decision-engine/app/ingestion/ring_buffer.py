# services\decision-engine\app\ingestion\ring_buffer.py
"""
In-memory rolling buffer of the last N seconds of telemetry per service.
When an anomaly fires, we slice this to build the snapshot window.
"""
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from app.config import settings

def _as_utc(ts: datetime | str) -> datetime:
    """Force any datetime or ISO timestamp to timezone-aware UTC."""
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _normalise_key(value: str) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def resolve_buffer_key(service_id: str, buffer: "TelemetryRingBuffer | None" = None) -> str | None:
    """Resolve a service id to the key actually used by the ring buffer."""
    buf = buffer or ring_buffer
    keys = list(buf.infra.keys()) + list(buf.app.keys())
    if not keys:
        return None
    if service_id in keys:
        return service_id

    needle = _normalise_key(service_id)
    for key in keys:
        if _normalise_key(key) == needle:
            return key

    try:
        from app.integration.catalog import resolve_catalog

        entry = resolve_catalog().get(service_id, {})
        name = entry.get("display_name") or entry.get("service_name")
        if name:
            wanted = _normalise_key(name)
            for key in keys:
                if _normalise_key(key) == wanted:
                    return key
    except Exception:
        pass

    for key in keys:
        candidate = _normalise_key(key)
        if needle and (needle in candidate or candidate in needle):
            return key
    return None


class TelemetryRingBuffer:
    def __init__(self, retention_seconds: int = None):
        self.retention = timedelta(
            seconds=retention_seconds or settings.RING_BUFFER_RETENTION_SEC
        )
        self.infra: dict[str, deque] = {}
        self.app: dict[str, deque] = {}
        self._last_infra_ts: dict[str, datetime] = {}
        self._last_app_ts: dict[str, datetime] = {}
        self._lock = Lock()

    def push_infra(self, service_id, timestamp, data):
        timestamp = _as_utc(timestamp)
        with self._lock:
            last = self._last_infra_ts.get(service_id)
            if last is not None and timestamp <= last:
                return
            buf = self.infra.setdefault(service_id, deque())
            buf.append({"time": timestamp, "data": data})
            self._last_infra_ts[service_id] = timestamp
            self._trim(buf)

    def push_app(self, service_id, timestamp, data):
        timestamp = _as_utc(timestamp)
        with self._lock:
            last = self._last_app_ts.get(service_id)
            if last is not None and timestamp <= last:
                return
            buf = self.app.setdefault(service_id, deque())
            buf.append({"time": timestamp, "data": data})
            self._last_app_ts[service_id] = timestamp
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