"""
train.py — Component 1: train and evaluate the HST anomaly detection model (single entity CLI).

Scope: warm up river's HalfSpaceTrees on one SMD entity's training split, score the
held-out test split, evaluate against ground truth, and save the trained model. The
actual work happens in src/pipeline.py's train_and_evaluate(), shared with
sweep_hyperparams.py and train_all.py.

Explicitly NOT in scope here (a teammate's work, see docs/Component_1_2_Technical_Guide.md):
  - the live streaming data generator ("Component 2" territory)
  - ADWIN drift detection / MLflow rollback ("Component 2: dynamic model updating")

Usage:
    uv run python train.py --entity machine-1-1
    uv run python train.py --entity machine-1-1 --eval-threshold 0.5
"""

import argparse
import logging
import sys

from src.config import HST_CFG, PIPELINE_CFG
from src.pipeline import train_and_evaluate

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
        "--eval-threshold",
        type=float,
        default=PIPELINE_CFG.eval_threshold,
        help="Score threshold for anomaly prediction (ignored if --calibrate is set)",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Calibrate a per entity threshold from held out normal data instead of "
             "using --eval-threshold. See RESULTS.md: a single fixed threshold does "
             "not transfer well across entities.",
    )
    parser.add_argument(
        "--calib-percentile",
        type=float,
        default=97,
        help="Percentile of held out calibration scores to use as the threshold "
             "when --calibrate is set (default 97, the recommended middle ground "
             "from the calibration sweep in RESULTS.md)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.calibrate:
        logger.info("Component 1 training run entity=%s calibrate=True percentile=%s",
                    args.entity, args.calib_percentile)
    else:
        logger.info("Component 1 training run entity=%s threshold=%s",
                    args.entity, args.eval_threshold)

    result = train_and_evaluate(
        args.entity, HST_CFG,
        eval_threshold=args.eval_threshold,
        calibrate=args.calibrate,
        calib_percentile=args.calib_percentile,
    )

    logger.info("warm up events=%s throughput=%.0f events per sec",
                result["warm_up_events"], result["warm_up_throughput_eps"])
    logger.info("precision=%.4f recall=%.4f f1=%.4f",
                result["precision"], result["recall"], result["f1"])
    logger.info("saved model to %s/%s and scores to %s/%s_scores.csv",
                PIPELINE_CFG.model_snapshot_dir, args.entity,
                PIPELINE_CFG.score_output_dir, args.entity)


if __name__ == "__main__":
    main()
