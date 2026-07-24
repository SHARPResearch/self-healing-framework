"""
sweep_hyperparams.py — Component 1: one at a time hyperparameter sensitivity sweep.

Varies n_trees, height, and window_size one at a time around the current baseline
(HST_CFG in .env), holding the other two fixed, instead of a full grid, to keep total
runtime reasonable. Runs on a single tuning entity (default machine-1-1).

Usage:
    uv run python sweep_hyperparams.py
    uv run python sweep_hyperparams.py --entity machine-2-1
"""

import argparse
import logging
import sys
import time
from dataclasses import replace

from src.config import HST_CFG, HSTConfig, PIPELINE_CFG
from src.evaluate import evaluate
from src.pipeline import warm_up_and_score

THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("sweep")


def build_grid() -> list:
    """One at a time sensitivity sweep: baseline, then each parameter varied alone."""
    baseline = HST_CFG
    return [
        replace(baseline),
        replace(baseline, n_trees=10),
        replace(baseline, n_trees=50),
        replace(baseline, height=10),
        replace(baseline, height=20),
        replace(baseline, window_size=150),
        replace(baseline, window_size=400),
    ]


def run_combo(entity_id: str, cfg: HSTConfig) -> dict:
    """
    Train one hyperparameter combination and find its best threshold.

    Trains once, then evaluates at every threshold in THRESHOLDS against the same
    scores (free), returning the threshold that gives the best F1 for this combo.
    Module level function so it can be pickled for ProcessPoolExecutor.
    """
    start = time.perf_counter()
    result = warm_up_and_score(entity_id, cfg)
    scores, labels = result["scores"], result["labels"]

    best = max(
        (evaluate(scores, labels, threshold=t) for t in THRESHOLDS),
        key=lambda m: m["f1"],
    )
    duration = time.perf_counter() - start

    return {
        "n_trees": cfg.n_trees,
        "height": cfg.height,
        "window_size": cfg.window_size,
        "best_threshold": best["threshold"],
        "precision": best["precision"],
        "recall": best["recall"],
        "f1": best["f1"],
        "duration_seconds": round(duration, 1),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Component 1: hyperparameter sweep")
    parser.add_argument(
        "--entity", default=PIPELINE_CFG.smd_entity, help="SMD entity ID to tune on"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    grid = build_grid()
    logger.info("Sweeping %s hyperparameter combinations on entity=%s", len(grid), args.entity)
    for cfg in grid:
        logger.info("  n_trees=%s height=%s window_size=%s", cfg.n_trees, cfg.height, cfg.window_size)


if __name__ == "__main__":
    main()
