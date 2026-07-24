"""
hst_model.py — Component 1: Half-Space Trees anomaly detection model.

Trains and scores river's HalfSpaceTrees anomaly detector on SMD telemetry. This module
owns the model only — data ingestion/streaming is a separate teammate's module
(docs/Component_1_2_Technical_Guide.md Part 3), and ADWIN drift detection / MLflow
rollback ("Component 2: dynamic model updating") is out of scope here.
"""

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
