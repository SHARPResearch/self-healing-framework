"""
evaluate.py — Component 1: evaluation of HST anomaly scores against SMD ground truth.

Pure functions only — no MLflow, no model state. train.py wires these into the
training run.
"""

from pathlib import Path
from typing import TypedDict

from sklearn.metrics import f1_score, precision_score, recall_score

from src.config import PIPELINE_CFG


class EvalMetrics(TypedDict):
    threshold: float
    precision: float
    recall: float
    f1: float
    n_predicted_anomalies: int
    n_actual_anomalies: int
    n_samples: int


def load_labels(entity_id: str) -> list[int]:
    """Load binary ground-truth anomaly labels for an SMD entity (test split only)."""
    label_path = Path(PIPELINE_CFG.smd_raw_dir) / "test_label" / f"{entity_id}.txt"
    if not label_path.exists():
        raise FileNotFoundError(f"Label file not found: {label_path}")

    with open(label_path) as f:
        return [int(line.strip()) for line in f if line.strip()]


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
