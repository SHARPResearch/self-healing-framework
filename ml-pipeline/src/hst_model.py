"""
hst_model.py — Component 1: Half-Space Trees anomaly detection model.

Trains and scores river's HalfSpaceTrees anomaly detector on SMD telemetry. This module
owns the model only — data ingestion/streaming is a separate teammate's module
(docs/Component_1_2_Technical_Guide.md Part 3), and ADWIN drift detection / MLflow
rollback ("Component 2: dynamic model updating") is out of scope here.
"""

import time
from dataclasses import dataclass
from typing import Iterable

from river.anomaly import HalfSpaceTrees

from src.config import HSTConfig


def build_model(cfg: HSTConfig) -> HalfSpaceTrees:
    """Construct a HalfSpaceTrees instance from the given hyperparameters."""
    return HalfSpaceTrees(
        n_trees=cfg.n_trees,
        height=cfg.height,
        window_size=cfg.window_size,
        seed=cfg.seed,
    )


@dataclass
class WarmUpStats:
    """Summary of a warm-up training pass over the training split."""
    n_events: int
    duration_seconds: float
    throughput_events_per_sec: float


def warm_up(model: HalfSpaceTrees, rows: Iterable[dict]) -> WarmUpStats:
    """
    Fit the model on training rows via learn_one() only (no scoring).

    Training data is assumed to be mostly-normal behaviour, so warm-up establishes
    what "normal" looks like before the model is used for detection.
    """
    start = time.perf_counter()
    n_events = 0
    for features in rows:
        model.learn_one(features)
        n_events += 1
    duration = time.perf_counter() - start
    throughput = n_events / duration if duration > 0 else 0.0
    return WarmUpStats(
        n_events=n_events,
        duration_seconds=round(duration, 2),
        throughput_events_per_sec=round(throughput, 1),
    )


def score_dataset(model: HalfSpaceTrees, rows: Iterable[dict]) -> list[float]:
    """
    Score rows against an already warmed-up model, clamped to [0, 1].

    The model is frozen here — only score_one() is called, never learn_one(). Continuing
    to learn during evaluation would blur "how well did the trained model do" with online
    adaptation, which is Component 2's job (ADWIN drift detection + rollback), not this
    module's.
    """
    return [float(min(max(model.score_one(features), 0.0), 1.0)) for features in rows]


def classify_severity(score: float) -> str:
    """
    Map a continuous anomaly score to the 4-level severity enum.

    Thresholds match services/decision-engine's PolicyEvaluator (see root CLAUDE.md
    "Anomaly severity thresholds" and docs/Doc1_Technical_Architecture.md §3.2).
    """
    if score < 0.5:
        return "watch"
    elif score < 0.7:
        return "warn"
    elif score < 0.85:
        return "degrade"
    else:
        return "critical"
