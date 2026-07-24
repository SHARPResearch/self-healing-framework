"""
train.py — Component 1: train and evaluate the HST anomaly detection model.

Scope: warm up river's HalfSpaceTrees on one SMD entity's training split, score the
held-out test split, evaluate against ground truth, and save the trained model.

Explicitly NOT in scope here (a teammate's work, see docs/Component_1_2_Technical_Guide.md):
  - the live streaming data generator ("Component 2" territory)
  - ADWIN drift detection / MLflow rollback ("Component 2: dynamic model updating")

Usage:
    uv run python train.py --entity machine-1-1
    uv run python train.py --entity machine-1-1 --eval-threshold 0.65
"""

import argparse
import csv
import logging
import pickle
import sys
from pathlib import Path

# Reuse datasets/smd/preprocess.py (canonical column renaming, already verified against
# the real SMD files) instead of duplicating a second loader here.
sys.path.insert(0, str(Path(__file__).parent.parent / "datasets" / "smd"))
from preprocess import preprocess_entity  # noqa: E402

import pandas as pd  # noqa: E402

from src.config import HST_CFG, PIPELINE_CFG  # noqa: E402
from src.evaluate import evaluate, load_labels  # noqa: E402
from src.hst_model import build_model, classify_severity, score_dataset, warm_up  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("train")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Component 1: train + evaluate the HST model")
    parser.add_argument(
        "--entity", default=PIPELINE_CFG.smd_entity, help="SMD entity ID, e.g. machine-1-1"
    )
    parser.add_argument(
        "--eval-threshold", type=float, default=0.7, help="Score threshold for anomaly prediction"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info("Component 1 training run -- entity=%s", args.entity)

    logger.info("[1/5] Preprocessing SMD data...")
    train_path = preprocess_entity(args.entity, split="train")
    test_path = preprocess_entity(args.entity, split="test")
    logger.info("  train=%s test=%s", train_path, test_path)

    train_df = pd.read_parquet(train_path)
    test_df = pd.read_parquet(test_path)
    logger.info("  train=%s rows, test=%s rows", len(train_df), len(test_df))

    logger.info("[2/5] Warming up HST model (n_trees=%s, height=%s, window_size=%s)...",
                HST_CFG.n_trees, HST_CFG.height, HST_CFG.window_size)
    model = build_model(HST_CFG)
    train_rows = train_df.to_dict(orient="records")
    warm_up_stats = warm_up(model, train_rows)
    logger.info("  %s events in %.1fs (%.0f events/sec)",
                warm_up_stats.n_events, warm_up_stats.duration_seconds,
                warm_up_stats.throughput_events_per_sec)

    logger.info("[3/5] Scoring test split (model frozen, no further learning)...")
    test_rows = test_df.to_dict(orient="records")
    scores = score_dataset(model, test_rows)
    severities = [classify_severity(s) for s in scores]
    logger.info("  scored %s rows, mean=%.4f max=%.4f",
                len(scores), sum(scores) / len(scores), max(scores))

    logger.info("[4/5] Evaluating against SMD ground-truth labels...")
    labels = load_labels(args.entity)
    metrics = evaluate(scores, labels, threshold=args.eval_threshold)
    logger.info("  precision=%.4f recall=%.4f f1=%.4f (threshold=%.2f)",
                metrics["precision"], metrics["recall"], metrics["f1"], metrics["threshold"])

    logger.info("[5/5] Saving trained model...")
    snapshot_dir = Path(PIPELINE_CFG.model_snapshot_dir) / args.entity
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    model_path = snapshot_dir / f"hst_model_step_{warm_up_stats.n_events}.pkl"
    model_path.write_bytes(pickle.dumps(model))
    logger.info("  saved %s (%.1f KB)", model_path, model_path.stat().st_size / 1024)

    score_dir = Path(PIPELINE_CFG.score_output_dir)
    score_dir.mkdir(parents=True, exist_ok=True)
    scores_path = score_dir / f"{args.entity}_scores.csv"
    with open(scores_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["step", "anomaly_score", "severity", "label"])
        for step, (score, severity, label) in enumerate(zip(scores, severities, labels), start=1):
            writer.writerow([step, round(score, 6), severity, label])
    logger.info("  saved %s (%s rows)", scores_path, len(scores))


if __name__ == "__main__":
    main()
