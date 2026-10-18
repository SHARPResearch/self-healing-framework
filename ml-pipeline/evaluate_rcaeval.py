"""
evaluate_rcaeval.py — Component 1 on real microservice failures: RCAEval RE1.

250 real fault-injection cases from two microservice systems running on Kubernetes under load
(RCAEval, Pham et al. 2025): Online Boutique (12 services, the same application this project's
live pipeline targets) and Sock Shop (15 services). Each case holds 1-second Prometheus/cAdvisor
metrics of every service, a period of normal operation, then a CPU hog, memory leak, disk stress,
network delay or packet loss injected into one service at a known time.

Per case and detector (static, the Component 1 setting): the detector is warmed up and calibrated
(97th percentile of held-out normal scores, as everywhere else in this project) on the first 70% of
the normal period, then scores the remaining 30% of the normal period and the whole fault period,
frozen. Nothing is tuned on RCAEval. The HST window is set to a fifth of the warm-up fit data
(at least 25), because these normal periods are far shorter than SMD's.

Per-case metrics:
  detected      any alarm after the injection
  delay_s       seconds from the injection to the first alarm (None if never)
  pre_fa_rate   alarm rate on the held-out normal part (false alarms per normal second)
  mcc, pr_auc   point-wise, label = after the injection

Usage:
  uv run python evaluate_rcaeval.py
  uv run python evaluate_rcaeval.py --systems RE1-OB --detectors pca_s5 lazy_range
"""

import argparse
import csv
import logging
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, matthews_corrcoef

sys.path.insert(0, str(Path(__file__).parent.parent / "datasets" / "rcaeval"))
from rcaeval_preprocess import list_cases, load_case  # noqa: E402

from src.hst_model import DETECTOR_PRESETS, build_model, detector_config, freeze_scaler  # noqa: E402
from src.lifecycle_manager import prepare_calibration  # noqa: E402

logger = logging.getLogger("evaluate_rcaeval")

DETECTORS = ["lazy_range", "lazy_range_ens", "pca", "pca_s5"]
TRAIN_SHARE_OF_NORMAL = 0.7
FIELDS = ["system", "case", "fault", "service", "detector", "n_features", "detected", "delay_s",
          "pre_fa_rate", "mcc", "pr_auc", "informedness", "duration_s"]


def evaluate_case(case_dir: Path, detector: str) -> dict:
    X, y, inject = load_case(case_dir)
    rows = X.to_dict(orient="records")
    n_train = int(inject * TRAIN_SHARE_OF_NORMAL)
    split = int(n_train * 0.8)
    cfg = replace(detector_config(detector), window_size=max(25, split // 5))

    t0 = time.perf_counter()
    model = build_model(cfg)
    for r in rows[:split]:
        model.learn_one(r)
    prepare_calibration(model, rows[:split], rows[split:n_train])
    calib = [float(min(max(model.score_one(r), 0.0), 1.0)) for r in rows[split:n_train]]
    for r in rows[split:n_train]:
        model.learn_one(r)
    freeze_scaler(model)
    threshold = float(np.percentile(calib, 97))

    scores = np.array([float(min(max(model.score_one(r), 0.0), 1.0)) for r in rows[n_train:]])
    labels = y[n_train:]
    alarms = scores >= threshold
    post = np.where(labels == 1)[0]
    post_alarms = alarms[post]
    first = int(np.argmax(post_alarms)) if post_alarms.any() else None
    pre_fa = float(alarms[labels == 0].mean()) if (labels == 0).any() else None
    recall = float(post_alarms.mean()) if len(post) else 0.0
    service, fault = case_dir.parent.name.rsplit("_", 1)
    return {
        "system": case_dir.parent.parent.name, "case": f"{case_dir.parent.name}/{case_dir.name}",
        "fault": fault, "service": service, "detector": detector, "n_features": X.shape[1],
        "detected": bool(post_alarms.any()), "delay_s": first,
        "pre_fa_rate": None if pre_fa is None else round(pre_fa, 4),
        "mcc": round(float(matthews_corrcoef(labels, alarms.astype(int))), 4),
        "pr_auc": round(float(average_precision_score(labels, scores)), 4),
        "informedness": round(recall - (pre_fa or 0.0), 4),
        "duration_s": round(time.perf_counter() - t0, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--systems", nargs="*", default=["RE1-OB", "RE1-SS"])
    parser.add_argument("--detectors", nargs="*", default=DETECTORS, choices=list(DETECTOR_PRESETS))
    parser.add_argument("--out", default="outputs/rcaeval/rcaeval_runs.csv")
    parser.add_argument("--limit", type=int, default=None, help="first N cases per system (smoke tests)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        with open(out, newline="") as f:
            done = {(r["system"], r["case"], r["detector"]) for r in csv.DictReader(f)}

    for system in args.systems:
        for case_dir in list_cases(system)[:args.limit]:
            key_case = f"{case_dir.parent.name}/{case_dir.name}"
            for detector in args.detectors:
                if (system, key_case, detector) in done:
                    continue
                row = evaluate_case(case_dir, detector)
                new = not out.exists()
                with open(out, "a", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=FIELDS)
                    if new:
                        w.writeheader()
                    w.writerow(row)
                logger.info("%s %-28s %-15s detected=%s delay=%s pre_fa=%s mcc=%.3f",
                            system, key_case, detector, row["detected"], row["delay_s"],
                            row["pre_fa_rate"], row["mcc"])

    df = pd.read_csv(out)
    summary = df.groupby(["system", "detector"]).agg(
        cases=("case", "count"), detected=("detected", "mean"), delay_median_s=("delay_s", "median"),
        pre_fa_rate=("pre_fa_rate", "mean"), mcc=("mcc", "mean"), pr_auc=("pr_auc", "mean"),
        informedness=("informedness", "mean")).round(4)
    print(summary.to_string())


if __name__ == "__main__":
    main()
