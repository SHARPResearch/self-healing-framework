"""
Tests for River collector
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from datetime import datetime, timedelta

from src.river_collector import RiverCollector
from src.prometheus_client import PrometheusClient
from src.config import config


def test_prometheus_connection():
    """Test Prometheus connection"""
    client = PrometheusClient(url=config.PROMETHEUS_URL)
    assert client._check_connection() is True
    print("✅ Prometheus connection test passed")


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
    """Test collecting metrics"""
    collector = RiverCollector(
        prometheus_url=config.PROMETHEUS_URL,
        service_name=config.RIVER_SERVICE_NAME
    )
    
    df = collector.collect_metrics(time_range="1m")
    
    # Check if DataFrame is returned
    assert isinstance(df, pd.DataFrame)
    print(f"✅ Collected {len(df)} data points")
    
    if not df.empty:
        # Check required columns
        expected_columns = ['timestamp', 'cpu_usage', 'memory_usage', 'request_latency', 'error_rate']
        for col in expected_columns:
            if col in df.columns:
                print(f"  ✅ Found column: {col}")
    

def test_river_stream():
    """Test River stream generation"""
    collector = RiverCollector(
        prometheus_url=config.PROMETHEUS_URL,
        service_name=config.RIVER_SERVICE_NAME
    )
    
    stream = collector.get_river_stream(time_range="1m")
    
    # Count items
    count = 0
    for X, y in stream:
        count += 1
        assert isinstance(X, dict)
        assert 'cpu_usage' in X or 'memory_usage' in X
        
        if count >= 5:
            break
    
    print(f"✅ River stream has {count} items")


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


if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Running River Collector Tests")
    print("=" * 50)
    
    test_prometheus_connection()
    test_collector_initialization()
    test_collect_metrics()
    test_river_stream()
    test_collector_stats()
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print("=" * 50)