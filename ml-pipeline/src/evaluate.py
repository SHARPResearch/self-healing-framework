"""
evaluate.py — Component 1: evaluation of HST anomaly scores against SMD ground truth.

Pure functions only — no MLflow, no model state. train.py wires these into the
training run.
"""

from pathlib import Path
from typing import TypedDict

import numpy as np
from sklearn.metrics import (
    average_precision_score, f1_score, precision_recall_curve, precision_score, recall_score,
)

from src.config import PIPELINE_CFG


class EvalMetrics(TypedDict):
    threshold: float
    precision: float
    recall: float
    f1: float
    n_predicted_anomalies: int
    n_actual_anomalies: int
    n_samples: int


class OracleResult(TypedDict):
    threshold: float
    precision: float
    recall: float
    f1: float


def load_labels(entity_id: str) -> list[int]:
    """Load binary ground-truth anomaly labels for an SMD entity (test split only)."""
    label_path = Path(PIPELINE_CFG.smd_raw_dir) / "test_label" / f"{entity_id}.txt"
    if not label_path.exists():
        raise FileNotFoundError(f"Label file not found: {label_path}")

    with open(label_path) as f:
        return [int(line.strip()) for line in f if line.strip()]


def pr_auc(scores: list[float], labels: list[int]) -> float:
    """
    Precision-recall AUC (average precision), threshold-independent ranking quality.

    Use this instead of ROC-AUC for anomaly detection: positives are rare (SMD is
    roughly 5-10% anomalous), and PR-AUC is not inflated by the large number of easy
    true negatives the way ROC-AUC can be on imbalanced data.
    """
    return round(float(average_precision_score(labels, scores)), 4)


def percentile_threshold(scores: list[float], percentile: float) -> float:
    """
    The score at the given percentile of a (presumed mostly-normal) score distribution.

    Used to calibrate a per-entity anomaly threshold from held-out normal data instead
    of reusing one fixed absolute cutoff across entities with different score scales.
    """
    return float(np.percentile(scores, percentile))


def oracle_best_f1(scores: list[float], labels: list[int]) -> OracleResult:
    """
    Best F1 achievable on this data, diagnostic upper bound only, NOT deployable.

    Uses the test labels to pick the threshold, which a real system cannot do at
    inference time. Purpose is to show how much of the precision/recall gap is closed
    by calibration versus how much would need a better model or features to close.
    Efficient: uses precision_recall_curve's O(n log n) sweep instead of scoring every
    candidate threshold with evaluate(), which would be O(n^2) for large score arrays.
    """
    precisions, recalls, thresholds = precision_recall_curve(labels, scores)
    f1s = np.where(
        (precisions + recalls) > 0,
        2 * precisions * recalls / (precisions + recalls + 1e-12),
        0.0,
    )
    # precision_recall_curve returns one more precision/recall point than thresholds
    # (the last point is the "threshold above everything" edge case with no threshold).
    best_idx = int(np.argmax(f1s[:-1]))
    return OracleResult(
        threshold=round(float(thresholds[best_idx]), 4),
        precision=round(float(precisions[best_idx]), 4),
        recall=round(float(recalls[best_idx]), 4),
        f1=round(float(f1s[best_idx]), 4),
    )


def evaluate(scores: list[float], labels: list[int], threshold: float = 0.7) -> EvalMetrics:
    """
    Threshold anomaly scores and compute precision/recall/F1 against ground truth.

    Args:
        scores: anomaly scores from score_dataset(), one per test row.
        labels: binary ground-truth labels from load_labels(), same length as scores.
        threshold: score >= threshold is predicted anomalous (default matches the
            "degrade" severity boundary, docs/Doc1_Technical_Architecture.md §3.2).
    """
    if len(scores) != len(labels):
        raise ValueError(f"Score/label length mismatch: {len(scores)} vs {len(labels)}")

    predicted = [1 if s >= threshold else 0 for s in scores]

    return {
        "threshold": threshold,
        "precision": round(precision_score(labels, predicted, zero_division=0), 4),
        "recall": round(recall_score(labels, predicted, zero_division=0), 4),
        "f1": round(f1_score(labels, predicted, zero_division=0), 4),
        "n_predicted_anomalies": sum(predicted),
        "n_actual_anomalies": sum(labels),
        "n_samples": len(scores),
    }
