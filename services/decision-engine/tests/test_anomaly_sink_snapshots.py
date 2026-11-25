from datetime import datetime, timedelta, timezone

import pytest

from app.ingestion import anomaly_sink
from app.ingestion.ring_buffer import TelemetryRingBuffer, resolve_buffer_key
from app.ingestion.telemetry_puller import _app_payload, _infra_payload


class FakeTimescale:
    def __init__(self):
        self.infra = []
        self.app = []

    async def insert_infra_snapshot(self, **kwargs):
        self.infra.append(kwargs)

    async def insert_app_snapshot(self, **kwargs):
        self.app.append(kwargs)


class FakePostgres:
    def __init__(self):
        self.captured = None
        self.failed = False

    async def mark_snapshot_captured(self, *args):
        self.captured = args

    async def mark_snapshot_failed(self, *args):
        self.failed = True


def _payload(value):
    return {"cpu": {"usage_pct": value}, "latency_ms": {"p99": value * 100}}


@pytest.mark.asyncio
async def test_phase1_and_phase2_store_before_and_after_windows(monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    buffer = TelemetryRingBuffer(retention_seconds=3600)
    for offset in (-120, -60, 60, 120):
        timestamp = now + timedelta(seconds=offset)
        buffer.push_infra("svc-a", timestamp, _payload(offset))
        buffer.push_app("svc-a", timestamp, _payload(offset))

    timescale = FakeTimescale()
    postgres = FakePostgres()
    monkeypatch.setattr(anomaly_sink, "ring_buffer", buffer)
    monkeypatch.setattr(anomaly_sink, "timescale_store", timescale)
    monkeypatch.setattr(anomaly_sink, "postgres_store", postgres)
    monkeypatch.setattr(anomaly_sink.settings, "SNAPSHOT_BEFORE_SEC", 180)
    monkeypatch.setattr(anomaly_sink.settings, "SNAPSHOT_AFTER_SEC", 180)

    await anomaly_sink._capture_phase1("ANM-1", "svc-a", now)
    before = sorted(point["time_"] for point in timescale.infra)
    assert before == [now - timedelta(seconds=120), now - timedelta(seconds=60)]

    await anomaly_sink._capture_phase2("ANM-1", "svc-a", now)
    after = sorted(point["time_"] for point in timescale.infra if point["time_"] >= now)
    assert after == [now + timedelta(seconds=60), now + timedelta(seconds=120)]
    assert postgres.captured is not None
    assert postgres.failed is False


def test_resolve_buffer_key_normalises_separators():
    buffer = TelemetryRingBuffer(retention_seconds=3600)
    buffer.push_infra("service-a-auth", datetime.now(timezone.utc), {})
    assert resolve_buffer_key("SERVICE_A_AUTH", buffer) == "service-a-auth"


def test_ring_buffer_ignores_duplicate_and_older_timestamps():
    buffer = TelemetryRingBuffer(retention_seconds=3600)
    now = datetime.now(timezone.utc)
    buffer.push_infra("svc-a", now, {"v": 1})
    buffer.push_infra("svc-a", now, {"v": 1})
    buffer.push_infra("svc-a", now - timedelta(seconds=5), {"v": 0})
    buffer.push_infra("svc-a", now + timedelta(seconds=5), {"v": 2})
    assert len(buffer.infra["svc-a"]) == 2
    assert [point["data"]["v"] for point in buffer.infra["svc-a"]] == [1, 2]


def test_c1_features_map_into_c2_snapshot_payloads():
    row = {
        "time": "2026-11-24T17:10:00+00:00",
        "features": {
            "cpu_rate": 0.25,
            "memory_used": 1073741824.0,
            "network_rx": 100.0,
            "network_tx": 40.0,
            "cpu_throttled": 0.1,
            "restarts": 2.0,
            "ready_ratio": 0.5,
        },
    }
    entry = {"replicas": 4, "display_name": "Cart", "mem_limit_mb": 1024.0}
    infra = _infra_payload("cartservice", row, entry)
    app = _app_payload("cartservice", row, entry)

    assert infra["pod_count"] == 4
    assert infra["ready_pods"] == 2
    assert infra["ready_ratio"] == 0.5
    assert infra["restarts_last_5m"] == 2
    assert infra["cpu"]["throttled_pct"] == 0.1
    assert infra["memory"]["pct"] == 1.0
    assert infra["network"]["rx_kbps"] == 0.8
    assert app["throughput_bytes_per_sec"] == 140.0
    assert app["latency_ms"] == {}
    assert app["error_rate"] is None
