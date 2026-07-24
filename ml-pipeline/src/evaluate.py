"""
evaluate.py — Component 1: evaluation of HST anomaly scores against SMD ground truth.

Pure functions only — no MLflow, no model state. train.py wires these into the
training run.
"""

from pathlib import Path

from src.config import PIPELINE_CFG


def load_labels(entity_id: str) -> list[int]:
    """Load binary ground-truth anomaly labels for an SMD entity (test split only)."""
    label_path = Path(PIPELINE_CFG.smd_raw_dir) / "test_label" / f"{entity_id}.txt"
    if not label_path.exists():
        raise FileNotFoundError(f"Label file not found: {label_path}")

    with open(label_path) as f:
        return [int(line.strip()) for line in f if line.strip()]
