# def main():
#     print("Hello from component-1-2-pipeline!")


# if __name__ == "__main__":
#     main()


"""
Main entry point for ml-pipeline
"""

import asyncio
import logging
import sys
from datetime import datetime

from src.config import config
from src.river_collector import RiverCollector
from src.prometheus_client import PrometheusClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_prometheus():
    """Test Prometheus connection"""
    logger.info("🔌 Testing Prometheus connection...")
    
    client = PrometheusClient(url=config.PROMETHEUS_URL)
    
    # Get metrics list
    metrics = client.get_metrics_list()
    logger.info(f"✅ Found {len(metrics)} metrics")
    
    # Get targets
    targets = client.get_targets()
    logger.info(f"✅ Found {len(targets)} targets")
    
    return client


def test_collector():
    """Test River collector"""
    logger.info("📊 Testing River collector...")
    
    collector = RiverCollector(
        prometheus_url=config.PROMETHEUS_URL,
        service_name=config.RIVER_SERVICE_NAME,
        batch_size=config.RIVER_BATCH_SIZE,
        poll_interval=config.RIVER_POLL_INTERVAL
    )
    
    # Collect metrics
    df = collector.get_dataframe(time_range="1m")
    
    if df.empty:
        logger.warning("⚠️ No data collected. Check Prometheus connection.")
        return
    
    logger.info(f"✅ Collected {len(df)} data points")
    logger.info(f"✅ Columns: {df.columns.tolist()}")
    logger.info(f"✅ Data sample:\n{df.head()}")
    
    # Get River stream
    stream = collector.get_river_stream(time_range="1m")
    
    # Count items in stream
    count = 0
    for X, y in stream:
        count += 1
        if count <= 3:
            logger.info(f"  Stream sample {count}: {X}")
    
    logger.info(f"✅ River stream has {count} items")
    
    return collector


def test_streaming():
    """Test streaming (async)"""
    logger.info("🌊 Testing streaming...")
    
    collector = RiverCollector(
        prometheus_url=config.PROMETHEUS_URL,
        service_name=config.RIVER_SERVICE_NAME,
        batch_size=5,  # Small batch for testing
        poll_interval=10  # Poll every 10 seconds
    )
    
    # Register callback
    def on_data(point):
        logger.info(f"  📍 Data point: {point['features']}")
    
    def on_batch(batch):
        logger.info(f"  📦 Batch of {len(batch)} points")
    
    collector.register_on_data(on_data)
    collector.register_on_batch(on_batch)
    
    # Run streaming
    try:
        # For demo, just run for 30 seconds
        import threading
        import time
        
        def run_stream():
            asyncio.run(collector.start_streaming())
        
        # Start in background thread
        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()
        
        # Let it run for 30 seconds
        time.sleep(30)
        collector.stop_streaming()
        
        logger.info(f"✅ Streaming stats: {collector.get_stats()}")
        
    except KeyboardInterrupt:
        collector.stop_streaming()
        logger.info("Streaming stopped")


def main():
    """Main function"""
    logger.info("🚀 Starting ml-pipeline")
    logger.info(f"📋 Config: Prometheus={config.PROMETHEUS_URL}")
    logger.info(f"📋 Config: Service={config.RIVER_SERVICE_NAME}")
    
    # Test Prometheus connection
    test_prometheus()
    
    # Test collector
    test_collector()
    
    # Test streaming
    print("\n" + "=" * 50)
    print("Testing streaming (will run for 30 seconds)...")
    print("=" * 50)
    test_streaming()
    
    print("\n" + "=" * 50)
    print("✅ All tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    main()