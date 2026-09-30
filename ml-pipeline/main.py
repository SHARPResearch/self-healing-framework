"""
Main entry point: Dynamic Model Updating for Microservices.

Bridges Kubernetes telemetry (online-boutique) from Prometheus to River's MinMaxScaler + HalfSpaceTrees (HST) Pipeline
and ADWIN drift detection in a 15-second real-time streaming loop.
"""

import logging
import random
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
    warmup_steps: int = 250,
    max_steps: Optional[int] = None,
):
    """
    Streaming loop that fetches Prometheus telemetry every 15 seconds,
    passes the observation dictionary to processor.process_one(), logs the anomaly score,
    and prints a warning if ADWIN's drift_detected flag evaluates to True.
    """
    logger.info("=" * 75)
    logger.info("🚀 STARTING REAL-TIME KUBERNETES -> RIVER PIPELINE STREAMING LOOP")
    logger.info(f"📍 Prometheus: {prometheus_url} | Namespace: {namespace} | Interval: {interval_seconds}s")
    logger.info("=" * 75)

    # 1. Initialize HSTStreamProcessor wrapper (wraps MinMaxScaler + HST Pipeline + ADWIN delta=0.002)
    if processor is None:
        processor = HSTStreamProcessor(
            service_id=namespace,
            hst_cfg=APP_CONFIG.hst,
            adwin_cfg=APP_CONFIG.adwin,
            with_scaler=True,
        )

    # 2. Reference window warm-up (at least 250 steps to fill HST reference window)
    if processor.step == 0:
        logger.info(f"🔥 Warming up HST reference window with {warmup_steps} baseline observations...")
        initial_telemetry = fetch_k8s_telemetry(prometheus_url=prometheus_url, namespace=namespace)
        
        # If cluster is live, sample baseline telemetry with small natural variations (+-3%)
        if any(v > 0 for v in initial_telemetry.values()):
            random.seed(42)
            for step_i in range(warmup_steps):
                jittered_obs = {
                    k: max(0.0, float(v) * random.uniform(0.97, 1.03))
                    for k, v in initial_telemetry.items()
                }
                processor.model.learn_one(jittered_obs)
            processor.take_stable_snapshot()
            logger.info(
                f"✅ Reference window filled ({warmup_steps} baseline events fitted). "
                f"MinMaxScaler & HalfSpaceTrees baseline established."
            )
        else:
            warmup_stream = stream_synthetic_telemetry(n_steps=warmup_steps, service_id=namespace, inject_anomaly_at=None)
            processor.warm_up(warmup_stream)

    step_count = 0

    logger.info("\n🟢 Model baseline is warm and monitoring live Kubernetes telemetry...")
    logger.info("👉 You can now inject chaos or scale down payment-service to observe anomaly detection and ADWIN drift.\n")

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
                f"Anomaly Score: {event.anomaly_score:.4f} | "
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
        warmup_steps=250,
    )


if __name__ == "__main__":
    main()