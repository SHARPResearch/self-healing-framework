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
import logging
import sys

from src.config import HST_CFG, PIPELINE_CFG

CANDIDATE_PERCENTILES = [90, 95, 97, 99, 99.5]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("calibrate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Component 1: per entity threshold calibration")
    parser.add_argument("--entity", help="Run a single entity instead of all 28")
    return parser.parse_args()
