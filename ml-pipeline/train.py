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
import logging
import sys
from pathlib import Path

# Reuse datasets/smd/preprocess.py (canonical column renaming, already verified against
# the real SMD files) instead of duplicating a second loader here.
sys.path.insert(0, str(Path(__file__).parent.parent / "datasets" / "smd"))
from preprocess import preprocess_entity  # noqa: E402

from src.config import PIPELINE_CFG  # noqa: E402

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


if __name__ == "__main__":
    main()
