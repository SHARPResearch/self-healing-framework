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
import csv
import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "datasets" / "smd"))
from preprocess import preprocess_entity  # noqa: E402

from src.config import HST_CFG, HSTConfig, PIPELINE_CFG  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.pipeline import warm_up_and_score  # noqa: E402

THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("sweep")


def build_grid() -> list:
    """
    One at a time sensitivity sweep: baseline, then each parameter varied alone.

    height=18 (not 20): HalfSpaceTrees builds 2^height nodes per tree up front, so
    height is exponential in cost, not linear. height=20 measured at roughly 640
    seconds of tree construction alone versus 20 seconds at the baseline height=15,
    and running that alongside other combos is what exhausted 16GB of RAM earlier.
    height=18 (8x the baseline node count) still shows sensitivity without that.
    """
    baseline = HST_CFG
    return [
        replace(baseline),
        replace(baseline, n_trees=10),
        replace(baseline, n_trees=50),
        replace(baseline, height=10),
        replace(baseline, height=18),
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
    logger.info("Sweeping %s hyperparameter combinations on entity=%s in parallel",
                len(grid), args.entity)

    # Preprocess once, serially, before spawning workers. All combos share the same
    # entity's cached parquet files; if it were not already cached, letting every
    # worker call preprocess_entity() concurrently could race to write it, corrupting
    # the file (this happened once when an earlier interrupted run left a partial
    # write on disk).
    logger.info("Pre warming preprocessed data cache for %s", args.entity)
    preprocess_entity(args.entity, split="train")
    preprocess_entity(args.entity, split="test")

    # HalfSpaceTrees memory scales with n_trees x 2^height x window_size. This machine
    # only has a few GB genuinely free at any time (other applications already use most
    # of the 16GB installed), so even 3 workers repeatedly drove free memory under 1GB.
    # 2 workers stays comfortably within the real headroom, at the cost of some wall
    # clock time.
    max_workers = min(2, len(grid))
    logger.info("Using %s parallel workers (memory bound, not cpu bound)", max_workers)
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(run_combo, args.entity, cfg) for cfg in grid]
        results = [f.result() for f in futures]

    results.sort(key=lambda r: r["f1"], reverse=True)

    out_path = Path(PIPELINE_CFG.score_output_dir) / "hyperparam_sweep.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    logger.info("Results (best first), saved to %s", out_path)
    for r in results:
        logger.info(
            "  n_trees=%-3s height=%-3s window_size=%-4s best_threshold=%.1f "
            "precision=%.4f recall=%.4f f1=%.4f (%.0fs)",
            r["n_trees"], r["height"], r["window_size"], r["best_threshold"],
            r["precision"], r["recall"], r["f1"], r["duration_seconds"],
        )


if __name__ == "__main__":
    main()
