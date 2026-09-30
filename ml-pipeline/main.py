"""
Main entry point for ml-pipeline: River Collector connected to Half-Space Trees (HST) Anomaly Detection & ADWIN Drift Detection.
"""

import asyncio
import logging
import sys
import threading
import time
from datetime import datetime

from src.config import APP_CONFIG, config
from src.data_pipeline import stream_synthetic_telemetry
from src.hst_model import HSTStreamProcessor, StreamEvent, classify_severity
from src.prometheus_client import PrometheusClient
from src.river_collector import RiverCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ml-pipeline")


def test_prometheus() -> PrometheusClient:
    """Test Prometheus connection"""
    logger.info("🔌 Testing Prometheus connection...")
    client = PrometheusClient(url=config.PROMETHEUS_URL)
    
    if client.is_connected:
        metrics = client.get_metrics_list()
        targets = client.get_targets()
        logger.info(f"✅ Connected to Prometheus! Found {len(metrics)} metrics and {len(targets)} targets")
    else:
        logger.warning(f"⚠️ Prometheus at {config.PROMETHEUS_URL} is unreachable (fallback mode available)")
    
    return client


def demo_river_to_hst_connection():
    """
    Demonstrate connecting the RiverCollector metrics stream to the HST model.
    """
    logger.info("=" * 60)
    logger.info("🚀 INITIALIZING RIVER PIPELINE -> HST MODEL INTEGRATION")
    logger.info("=" * 60)

    service_name = config.RIVER_SERVICE_NAME
    
    # 1. Instantiate the HST Stream Processor (Half-Space Trees + ADWIN)
    processor = HSTStreamProcessor(
        service_id=service_name,
        hst_cfg=APP_CONFIG.hst,
        adwin_cfg=APP_CONFIG.adwin,
    )

    # 2. Warm up HST on baseline normal telemetry
    logger.info(f"🔥 Warming up HST model for '{service_name}' on baseline telemetry...")
    warmup_stream = stream_synthetic_telemetry(n_steps=150, service_id=service_name, inject_anomaly_at=None)
    warmup_stats = processor.warm_up(warmup_stream)
    logger.info(
        f"✅ HST Model Warmed Up: {warmup_stats.n_events} baseline events fitted "
        f"at {warmup_stats.throughput_events_per_sec} events/sec"
    )

    # 3. Instantiate RiverCollector
    collector = RiverCollector(
        prometheus_url=config.PROMETHEUS_URL,
        service_name=service_name,
        batch_size=5,
        poll_interval=2,
    )

    # 4. Connect RiverCollector directly to the HST Stream Processor
    def on_hst_event(event: StreamEvent):
        status_emoji = "🟢" if event.severity == "watch" else ("🟡" if event.severity == "warn" else "🔴")
        drift_str = " 🚨 [ADWIN DRIFT DETECTED]" if event.drift_detected else ""
        logger.info(
            f"{status_emoji} [HST Event #{event.step:03d}] Service: {event.service_id} | "
            f"Score: {event.anomaly_score:.4f} | Severity: {event.severity.upper():<8} | "
            f"Latency: {event.latency_ms:.2f}ms{drift_str}"
        )

    collector.connect_hst_model(processor, on_event=on_hst_event)

    # 5. Stream telemetry through the connected River + HST pipeline
    logger.info("\n🌊 Streaming telemetry through River -> HST pipeline...")
    
    # If Prometheus has data, collect and score live metrics
    live_df = collector.collect_metrics(time_range="5m")
    if not live_df.empty:
        logger.info(f"📊 Processing {len(live_df)} live Prometheus metric points through HST...")
        for event in collector.stream_to_hst(processor, time_range="5m"):
            on_hst_event(event)
    else:
        logger.info("ℹ️ Using simulated streaming telemetry (normal traffic + anomalous surge at step 20)...")
        test_stream = stream_synthetic_telemetry(n_steps=40, service_id=service_name, inject_anomaly_at=20)
        for point_features in test_stream:
            # Emit into collector callback
            point = {
                "features": point_features,
                "timestamp": datetime.now(),
                "service": service_name,
            }
            for cb in collector.on_data_callbacks:
                cb(point)

    # 6. Display pipeline stats
    logger.info("=" * 60)
    logger.info("📊 PIPELINE SUMMARY & MONITORING STATS")
    logger.info("=" * 60)
    logger.info(f"Total Steps Processed  : {processor.step}")
    logger.info(f"ADWIN Drift Count      : {processor.drift_count}")
    logger.info(f"Rolling Mean Score     : {processor.rolling_mean_score:.4f}")
    logger.info(f"Rolling Max Score      : {processor.rolling_max_score:.4f}")
    logger.info(f"Warn / Violation Rate  : {processor.warn_rate * 100:.1f}%")
    logger.info(f"Collector Stats        : {collector.get_stats()}")
    logger.info("=" * 60)


def main():
    """Main execution entrypoint"""
    logger.info("🚀 Starting ml-pipeline...")
    logger.info(f"📋 Config: Prometheus={config.PROMETHEUS_URL}")
    logger.info(f"📋 Config: Service={config.RIVER_SERVICE_NAME}")

    # Check Prometheus
    test_prometheus()

    # Run the connected River -> HST pipeline
    demo_river_to_hst_connection()

    logger.info("✅ River pipeline -> HST model execution finished successfully!")


if __name__ == "__main__":
    main()