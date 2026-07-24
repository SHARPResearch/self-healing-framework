"""
train_all.py — Component 1: run training and evaluation across all 28 SMD entities.

Runs the same flow as train.py, in parallel across entities, and aggregates precision,
recall, and F1 so we can see whether machine-1-1 (the tuning entity) is an easy or hard
outlier compared to the rest. Does not save a model pickle or MLflow artifact per
entity (28 x ~50MB would be wasteful); logs params/metrics only.

Usage:
    uv run python train_all.py
    uv run python train_all.py --eval-threshold 0.4 --n-trees 25 --height 15 --window-size 250
"""

import argparse
import csv
import logging
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

from src.config import HST_CFG, HSTConfig, PIPELINE_CFG
from src.pipeline import train_and_evaluate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("train_all")


def discover_entities() -> list[str]:
    """List every SMD entity that has both a train and a test file."""
    raw_dir = Path(PIPELINE_CFG.smd_raw_dir)
    train_ids = {p.stem for p in (raw_dir / "train").glob("*.txt")}
    test_ids = {p.stem for p in (raw_dir / "test").glob("*.txt")}
    return sorted(train_ids & test_ids)


def run_one_entity(entity_id: str, cfg: HSTConfig, eval_threshold: float) -> dict:
    """
    Train and evaluate one entity, no model pickle, no MLflow artifact, metrics only.

    Module level function so it can be pickled for ProcessPoolExecutor.
    """
    result = train_and_evaluate(
        entity_id, cfg, eval_threshold,
        save_model=False, save_scores_csv=False, log_to_mlflow=True,
    )
    return {
        "entity_id": entity_id,
        "precision": result["precision"],
        "recall": result["recall"],
        "f1": result["f1"],
        "n_actual_anomalies": result["n_actual_anomalies"],
        "n_samples": result["n_samples"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Component 1: train across all SMD entities")
    parser.add_argument("--eval-threshold", type=float, default=PIPELINE_CFG.eval_threshold)
    parser.add_argument("--n-trees", type=int, default=HST_CFG.n_trees)
    parser.add_argument("--height", type=int, default=HST_CFG.height)
    parser.add_argument("--window-size", type=int, default=HST_CFG.window_size)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = replace(HST_CFG, n_trees=args.n_trees, height=args.height, window_size=args.window_size)
    entities = discover_entities()
    logger.info("Training %s entities in parallel, n_trees=%s height=%s window_size=%s threshold=%s",
                len(entities), cfg.n_trees, cfg.height, cfg.window_size, args.eval_threshold)

    # This machine's other applications already use most of the 16GB installed, and
    # the hyperparameter sweep repeatedly drove free memory under 1GB even at 2
    # workers. Going fully serial here too trades wall clock time (28 entities at
    # roughly 90 seconds each is under 45 minutes) for a run that reliably finishes.
    max_workers = 1
    logger.info("Using %s parallel workers (memory bound, not cpu bound)", max_workers)
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(run_one_entity, e, cfg, args.eval_threshold) for e in entities]
        results = []
        for i, future in enumerate(futures, start=1):
            r = future.result()
            results.append(r)
            logger.info("  [%s/%s] %s precision=%.4f recall=%.4f f1=%.4f",
                        i, len(entities), r["entity_id"], r["precision"], r["recall"], r["f1"])

    out_path = Path(PIPELINE_CFG.score_output_dir) / "all_entities_summary.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    f1s = [r["f1"] for r in results]
    precisions = [r["precision"] for r in results]
    recalls = [r["recall"] for r in results]
    logger.info("Saved per entity results to %s", out_path)
    logger.info("F1 across %s entities: mean=%.4f median=%.4f min=%.4f max=%.4f",
                len(f1s), statistics.mean(f1s), statistics.median(f1s), min(f1s), max(f1s))
    logger.info("Precision mean=%.4f, Recall mean=%.4f", statistics.mean(precisions), statistics.mean(recalls))


if __name__ == "__main__":
    main()
