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


# ── Component 2: concept drift scenarios for the dynamic updating evaluation ──────────────
#
# SMD has anomaly labels but no record of deployments, so the benign concept drift the
# lifecycle manager has to handle is injected: a persistent level shift on a random subset of
# features from a given step onward, standing in for "a release changed baseline resource use".
# Labels are untouched: a shifted normal point is still normal, and an anomaly inside the
# shifted regime is still an anomaly. Each injection can be announced by a change event
# (deployment) or left silent, which is what separates the "deploy" and "silent" scenarios.

from dataclasses import dataclass  # noqa: E402
import random  # noqa: E402

from src.change_events import ChangeEvent  # noqa: E402

SCENARIOS = ("none", "deploy", "silent", "noop_deploy")


@dataclass(frozen=True)
class DriftInjection:
    start: int                    # 0-based row index where the new regime begins
    features: tuple[str, ...]
    deltas: tuple[float, ...]     # additive shift per feature, result clipped to [0, 1]
    announced: bool               # emit a deployment change event at `start`


def make_scenario(
    scenario: str,
    test_df: pd.DataFrame,
    entity_id: str,
    seed: int = 0,
    starts: tuple[float, ...] = (0.35, 0.70),
    feature_fraction: float = 0.3,
    delta_range: tuple[float, float] = (0.2, 0.3),
) -> list[DriftInjection]:
    """
    Drift injections for one named scenario on one entity's test split.

      none         original data, no change events.
      deploy       a level shift at each of `starts` (fractions of the stream), each announced
                   by a deployment change event.
      silent       the same shifts, no change events (drift nobody told the model about).
      noop_deploy  deployment events at the same steps but no behaviour change (tests that
                   the model is not needlessly replaced).
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}, expected one of {SCENARIOS}")
    if scenario == "none":
        return []
    rng = random.Random(f"{entity_id}:{seed}")
    varying = [c for c in test_df.columns if float(test_df[c].std()) > 1e-6]
    n_pick = max(1, int(round(feature_fraction * len(varying))))
    injections = []
    for frac in starts:
        start = int(len(test_df) * frac)
        if scenario == "noop_deploy":
            injections.append(DriftInjection(start, (), (), announced=True))
            continue
        feats = tuple(sorted(rng.sample(varying, n_pick)))
        deltas = tuple(round(rng.uniform(*delta_range), 4) for _ in feats)
        injections.append(DriftInjection(start, feats, deltas, announced=(scenario == "deploy")))
    return injections


def apply_injections(test_df: pd.DataFrame, injections: list[DriftInjection]) -> pd.DataFrame:
    """Return a copy of `test_df` with every injection's shift applied from its start onward."""
    out = test_df.copy()
    for inj in injections:
        for feat, delta in zip(inj.features, inj.deltas):
            col = out.columns.get_loc(feat)
            out.iloc[inj.start:, col] = np.clip(out.iloc[inj.start:, col] + delta, 0.0, 1.0)
    return out


def change_events_for(injections: list[DriftInjection], service_id: str) -> list[ChangeEvent]:
    """Deployment change events for announced injections (1-based step, as the manager counts)."""
    return [
        ChangeEvent(service_id, "deployment", step=inj.start + 1,
                    detail={"features": list(inj.features)})
        for inj in injections if inj.announced
    ]
