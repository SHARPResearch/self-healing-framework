"""
Tests for River collector and its connection to the HST model
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from datetime import datetime, timedelta

from src.river_collector import RiverCollector
from src.prometheus_client import PrometheusClient
from src.config import config, HSTConfig, ADWINConfig
from src.hst_model import HSTStreamProcessor, StreamEvent, build_model
from src.data_pipeline import stream_synthetic_telemetry


def test_prometheus_connection():
    """Test Prometheus client initialization and connection check"""
    client = PrometheusClient(url=config.PROMETHEUS_URL)
    assert isinstance(client.is_connected, bool)
    print(f"✅ Prometheus connection status: {client.is_connected}")


def test_collector_initialization():
    """Test collector initialization"""
    collector = RiverCollector(
        prometheus_url=config.PROMETHEUS_URL,
        service_name="test-service",
        batch_size=50,
        poll_interval=30
    )
    assert collector.service_name == "test-service"
    assert collector.batch_size == 50
    assert collector.poll_interval == 30
    print("✅ Collector initialization test passed")


def test_collect_metrics():
    """Test collecting metrics returns DataFrame"""
    collector = RiverCollector(
        prometheus_url=config.PROMETHEUS_URL,
        service_name=config.RIVER_SERVICE_NAME
    )
    
    df = collector.collect_metrics(time_range="1m")
    assert isinstance(df, pd.DataFrame)
    print(f"✅ Collected {len(df)} data points")


def test_river_stream():
    """Test River stream generation format"""
    collector = RiverCollector(
        prometheus_url=config.PROMETHEUS_URL,
        service_name=config.RIVER_SERVICE_NAME
    )
    
    stream = collector.get_river_stream(time_range="1m")
    count = 0
    for X, y in stream:
        count += 1
        assert isinstance(X, dict)
        if count >= 5:
            break
    print(f"✅ River stream verified ({count} items)")


def test_collector_stats():
    """Test collector statistics"""
    collector = RiverCollector(
        prometheus_url=config.PROMETHEUS_URL,
        service_name=config.RIVER_SERVICE_NAME
    )
    
    stats = collector.get_stats()
    assert 'service' in stats
    assert 'is_running' in stats
    assert 'total_collected' in stats
    assert 'error_count' in stats
    print(f"✅ Collector stats: {stats}")


def test_connect_river_to_hst():
    """Test connecting RiverCollector directly to HSTStreamProcessor"""
    hst_cfg = HSTConfig(n_trees=5, height=5, window_size=50, seed=42)
    processor = HSTStreamProcessor(service_id="payment-service", hst_cfg=hst_cfg)
    
    # Warm up with baseline stream
    warmup_stream = stream_synthetic_telemetry(n_steps=30, service_id="payment-service", inject_anomaly_at=None)
    processor.warm_up(warmup_stream)
    
    collector = RiverCollector(
        prometheus_url=config.PROMETHEUS_URL,
        service_name="payment-service",
        batch_size=10,
        poll_interval=5,
    )
    
    emitted_events = []
    def event_handler(event: StreamEvent):
        emitted_events.append(event)
    
    collector.connect_hst_model(processor, on_event=event_handler)
    
    # Emit test points into collector
    test_points = [
        {"features": {"cpu_usage": 0.2, "memory_usage": 0.3, "request_latency": 0.05, "error_rate": 0.0}, "service": "payment-service"},
        {"features": {"cpu_usage": 0.95, "memory_usage": 0.98, "request_latency": 2.5, "error_rate": 0.5}, "service": "payment-service"},
    ]
    
    for pt in test_points:
        for cb in collector.on_data_callbacks:
            cb(pt)
            
    assert len(emitted_events) == 2
    assert processor.step == 2
    assert 0.0 <= emitted_events[0].anomaly_score <= 1.0
    assert emitted_events[0].severity in ["watch", "warn", "degrade", "critical"]
    print(f"✅ River to HST direct connection test passed (processed {len(emitted_events)} events)")


def test_hst_stream_processor_drift_and_snapshot():
    """Test HSTStreamProcessor online updating, ADWIN drift detection, and snapshots"""
    processor = HSTStreamProcessor(service_id="order-service")
    
    # Snapshot
    snapshot_bytes = processor.snapshot()
    assert isinstance(snapshot_bytes, bytes)
    
    # Process sequence with anomaly
    stream = stream_synthetic_telemetry(n_steps=60, service_id="order-service", inject_anomaly_at=30)
    events = list(processor.process_stream(stream))
    
    assert len(events) == 60
    assert processor.step == 60
    assert processor.rolling_mean_score >= 0.0
    
    # Restore from snapshot
    processor.restore(snapshot_bytes)
    assert processor.hst_model.n_trees == processor._hst_cfg.n_trees
    print("✅ HSTStreamProcessor drift and snapshot test passed")


if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Running River Collector & HST Integration Tests")
    print("=" * 50)
    
    test_prometheus_connection()
    test_collector_initialization()
    test_collect_metrics()
    test_river_stream()
    test_collector_stats()
    test_connect_river_to_hst()
    test_hst_stream_processor_drift_and_snapshot()
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print("=" * 50)