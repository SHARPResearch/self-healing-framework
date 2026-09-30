"""
Main entry point: Dynamic Model Updating for Microservices.

Bridges Kubernetes telemetry (online-boutique) from Prometheus to River's HalfSpaceTrees (HST)
and ADWIN drift detection in a 15-second real-time streaming loop.
"""

import logging
import sys
import time
from datetime import datetime
from typing import Dict, Optional

import requests

from src.config import APP_CONFIG, config
from src.data_pipeline import stream_synthetic_telemetry
from src.hst_model import HSTStreamProcessor, StreamEvent, classify_severity
from src.prometheus_client import PrometheusClient, fetch_k8s_telemetry
from src.river_collector import RiverCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ml-pipeline")


def run_streaming_loop(
    prometheus_url: str = "http://localhost:9090",
    namespace: str = "online-boutique",
    interval_seconds: int = 15,
    processor: Optional[HSTStreamProcessor] = None,
    max_steps: Optional[int] = None,
):
    """
    Streaming loop that fetches Prometheus telemetry every 15 seconds,
    passes the observation dictionary to processor.process_one(), logs the anomaly score,
    and prints a warning if ADWIN's drift_detected flag evaluates to True.
    """
    logger.info("=" * 70)
    logger.info("🚀 STARTING REAL-TIME KUBERNETES -> RIVER HST STREAMING LOOP")
    logger.info(f"📍 Prometheus: {prometheus_url} | Namespace: {namespace} | Interval: {interval_seconds}s")
    logger.info("=" * 70)

    # 1. Initialize HSTStreamProcessor wrapper (wraps HST + ADWIN delta=0.002)
    if processor is None:
        processor = HSTStreamProcessor(
            service_id=namespace,
            hst_cfg=APP_CONFIG.hst,
            adwin_cfg=APP_CONFIG.adwin,
        )

    # 2. Baseline warm-up check: if model is freshly initialized, warm up with baseline
    if processor.step == 0:
        logger.info(f"🔥 Warming up HST reference window with initial baseline observations...")
        initial_telemetry = fetch_k8s_telemetry(prometheus_url=prometheus_url, namespace=namespace)
        if any(v > 0 for v in initial_telemetry.values()):
            # Fit initial telemetry point as baseline
            for _ in range(50):
                processor.model.learn_one(initial_telemetry)
            processor.take_stable_snapshot()
            logger.info("✅ Baseline warm-up initialized from live cluster telemetry.")
        else:
            warmup_stream = stream_synthetic_telemetry(n_steps=50, service_id=namespace, inject_anomaly_at=None)
            processor.warm_up(warmup_stream)

    step_count = 0

    # 3. Continuous 15-second streaming loop
    try:
        while True:
            # Step A: Ingest Kubernetes telemetry from Prometheus API (/api/v1/query)
            telemetry: Dict[str, float] = fetch_k8s_telemetry(
                prometheus_url=prometheus_url,
                namespace=namespace,
            )

            # Step B: Pass data dictionary to process_one (score_one strictly before learn_one)
            event: StreamEvent = processor.process_one(telemetry)
            step_count += 1

            # Step C: Log the observation and anomaly score
            status_badge = "🟢 WATCH" if event.severity == "watch" else (
                "🟡 WARN" if event.severity == "warn" else (
                    "🟠 DEGRADE" if event.severity == "degrade" else "🔴 CRITICAL"
                )
            )
            logger.info(
                f"[{status_badge}] Step #{event.step:04d} | "
                f"Score: {event.anomaly_score:.4f} | "
                f"CPU: {telemetry.get('cpu_rate', 0.0):.4f} cores | "
                f"Mem: {telemetry.get('memory_usage', 0.0) / (1024 * 1024):.1f} MB | "
                f"Net Rx: {telemetry.get('network_receive_rate', 0.0) / 1024:.1f} KB/s | "
                f"Latency: {event.latency_ms:.2f}ms"
            )

            # Step D: Conditional block - alert if ADWIN concept drift detected
            if event.drift_detected or processor.adwin.drift_detected:
                print(
                    f"\n⚠️  [DRIFT DETECTED] ADWIN flagged significant concept drift in anomaly scores! "
                    f"(Step #{event.step}, Current Score={event.anomaly_score:.4f}, Drift Count={processor.drift_count})\n"
                )

            # Check max_steps termination (useful for automated testing)
            if max_steps is not None and step_count >= max_steps:
                logger.info(f"Reached max requested steps ({max_steps}). Exiting streaming loop.")
                break

            # Step E: Wait 15 seconds before next poll
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        logger.info("\n⏹️ Streaming loop gracefully stopped by user.")


def main():
    """Main application execution"""
    run_streaming_loop(
        prometheus_url=config.PROMETHEUS_URL,
        namespace="online-boutique",
        interval_seconds=15,
    )


if __name__ == "__main__":
    main()