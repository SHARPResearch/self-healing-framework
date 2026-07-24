"""
calibrate.py — Component 1: per entity threshold calibration versus the fixed global
threshold from the prior tuning pass.

The prior session found that EVAL_THRESHOLD=0.4 (tuned on machine-1-1) does not
transfer across the other 27 SMD entities: mean F1 across all 28 was 0.1195 versus
machine-1-1's own 0.5663. This script tests the fix: calibrate each entity's threshold
from its own held-out normal data (a percentile of held-out score distribution)
instead of reusing one shared absolute cutoff, and compares against both the known
fixed-threshold baseline and an oracle (non-deployable) upper bound.

Usage:
    uv run python calibrate.py
    uv run python calibrate.py --entity machine-1-1
"""

import argparse
import csv
import logging
import statistics
import sys
from pathlib import Path

from train_all import discover_entities

from src.config import HST_CFG, HSTConfig, PIPELINE_CFG
from src.evaluate import evaluate, oracle_best_f1, percentile_threshold, pr_auc
from src.pipeline import warm_up_calibrate_and_score

CANDIDATE_PERCENTILES = [90, 95, 97, 99, 99.5]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("calibrate")


def run_one_entity_calibration(entity_id: str, cfg: HSTConfig) -> dict:
    """
    Compute PR-AUC, percentile calibrated F1 for each candidate, and oracle best F1.

    Module level function so it can be reused directly (kept serial here, not pooled,
    per the memory exhaustion lesson from the previous hyperparameter sweep).
    """
    result = warm_up_calibrate_and_score(entity_id, cfg)
    calib_scores, test_scores, labels = (
        result["calib_scores"], result["test_scores"], result["labels"]
    )

    row = {
        "entity_id": entity_id,
        "pr_auc": pr_auc(test_scores, labels),
        "n_actual_anomalies": sum(labels),
        "n_samples": len(labels),
    }

    for p in CANDIDATE_PERCENTILES:
        threshold = percentile_threshold(calib_scores, p)
        metrics = evaluate(test_scores, labels, threshold=threshold)
        key = str(p).replace(".", "_")
        row[f"p{key}_threshold"] = round(threshold, 4)
        row[f"p{key}_precision"] = metrics["precision"]
        row[f"p{key}_recall"] = metrics["recall"]
        row[f"p{key}_f1"] = metrics["f1"]

    oracle = oracle_best_f1(test_scores, labels)
    row["oracle_threshold"] = oracle["threshold"]
    row["oracle_precision"] = oracle["precision"]
    row["oracle_recall"] = oracle["recall"]
    row["oracle_f1"] = oracle["f1"]

    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Component 1: per entity threshold calibration")
    parser.add_argument("--entity", help="Run a single entity instead of all 28")
    return parser.parse_args()


# Known from the prior tuning pass (ml-pipeline/RESULTS.md): mean F1 across all 28
# entities using the single fixed global EVAL_THRESHOLD=0.4 tuned on machine-1-1 alone.
FIXED_THRESHOLD_MEAN_F1 = 0.1195


def main() -> None:
    args = parse_args()
    entities = [args.entity] if args.entity else discover_entities()
    logger.info("Calibrating %s entities serially (memory bound, not cpu bound)", len(entities))

    rows = []
    for i, entity_id in enumerate(entities, start=1):
        row = run_one_entity_calibration(entity_id, HST_CFG)
        rows.append(row)
        logger.info("  [%s/%s] %s pr_auc=%.4f oracle_f1=%.4f p97_f1=%.4f",
                    i, len(entities), entity_id, row["pr_auc"], row["oracle_f1"], row["p97_f1"])

    out_path = Path(PIPELINE_CFG.score_output_dir) / "calibration_comparison.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Saved per entity calibration results to %s", out_path)

    logger.info("Mean F1 comparison across %s entities:", len(rows))
    logger.info("  fixed global threshold (known from prior run) = %.4f", FIXED_THRESHOLD_MEAN_F1)
    for p in CANDIDATE_PERCENTILES:
        key = str(p).replace(".", "_")
        mean_f1 = statistics.mean(r[f"p{key}_f1"] for r in rows)
        logger.info("  percentile=%s calibrated mean f1 = %.4f", p, mean_f1)
    oracle_mean = statistics.mean(r["oracle_f1"] for r in rows)
    logger.info("  oracle (non deployable upper bound) mean f1 = %.4f", oracle_mean)
    logger.info("  mean pr_auc = %.4f", statistics.mean(r["pr_auc"] for r in rows))


if __name__ == "__main__":
    main()
