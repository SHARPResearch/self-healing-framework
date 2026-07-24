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
from dataclasses import replace

from src.config import HST_CFG, PIPELINE_CFG

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
