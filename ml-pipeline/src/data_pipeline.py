"""
data_pipeline.py — Component 2: live streaming telemetry generators for HST consumption.
"""

import logging
import time
from typing import Generator, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def stream_entity(
    df: pd.DataFrame,
    entity_id: str = "default",
    delay_seconds: float = 0.0,
) -> Generator[dict[str, float], None, None]:
    """
    Yields one feature dict per iteration from a DataFrame.
    Matches the schema consumed by HSTStreamProcessor.score_and_learn().
    """
    n_rows = len(df)
    logger.info(f"Starting stream for {entity_id}: {n_rows} events.")

    for idx, row in enumerate(df.itertuples(index=False, name=None)):
        feature_dict: dict[str, float] = dict(zip(df.columns, (float(val) for val in row)))
        yield feature_dict

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    logger.info(f"Stream complete for {entity_id}: {n_rows} events processed.")


def stream_synthetic_telemetry(
    n_steps: int = 100,
    service_id: str = "order-service",
    inject_anomaly_at: Optional[int] = 50,
    delay_seconds: float = 0.0,
) -> Generator[dict[str, float], None, None]:
    """
    Generate synthetic Prometheus metric feature dicts for testing and simulation.
    """
    np.random.seed(42)
    for step in range(n_steps):
        is_anomaly = inject_anomaly_at is not None and step >= inject_anomaly_at
        
        cpu_usage = float(np.random.uniform(0.7, 0.99) if is_anomaly else np.random.uniform(0.1, 0.35))
        memory_usage = float(np.random.uniform(0.8, 0.98) if is_anomaly else np.random.uniform(0.2, 0.45))
        request_latency = float(np.random.uniform(0.5, 2.5) if is_anomaly else np.random.uniform(0.01, 0.08))
        error_rate = float(np.random.uniform(0.15, 0.6) if is_anomaly else 0.0)

        features = {
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "request_latency": request_latency,
            "error_rate": error_rate,
        }

        yield features

        if delay_seconds > 0:
            time.sleep(delay_seconds)
