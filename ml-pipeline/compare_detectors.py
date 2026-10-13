"""
compare_detectors.py — Component 1 v2: detector bake-off on all 28 SMD entities (static setting).

Every candidate gets the same calibrated warm-up as Component 1 (src/pipeline.py
warm_up_calibrate_and_score): learn the first 80% of the train split, set the threshold at the
97th percentile of frozen scores on the held-out last 20%, learn that 20% too, then score the
test split frozen. Only the detector differs.

Candidates:
  river           river HalfSpaceTrees + online MinMaxScaler (Component 1 as shipped)
  lazy            src/lazy_hst.py, same algorithm built on demand (scalability)
  lazy_range      lazy + limits widened to [-0.25, 1.25] + scaler frozen after warm-up
  lazy_range_ens  lazy_range rank-averaged with a robust per-feature deviation scorer

Selection rule, fixed before looking at results: choose on the dev entities (machine-1-*) by
mean PR-AUC, the threshold-free ranking quality; break ties (< 0.005) in favour of the simpler
and cheaper model. Held-out entities (machine-2-*, machine-3-*) are reported, not used to choose.

Outputs: outputs/detectors/detectors.csv (per entity x candidate), summary printed.

Usage:
  uv run python compare_detectors.py
  uv run python compare_detectors.py --entities machine-1-1 --candidates river lazy
"""

import argparse
import bisect
import csv
import logging
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import matthews_corrcoef

sys.path.insert(0, str(Path(__file__).parent.parent / "datasets" / "smd"))
from preprocess import discover_entities, preprocess_entity  # noqa: E402

from src.config import HST_CFG  # noqa: E402
from src.evaluate import evaluate, load_labels, oracle_best_f1, percentile_threshold, pr_auc  # noqa: E402
from src.hst_model import build_model, freeze_scaler  # noqa: E402

logger = logging.getLogger("compare_detectors")

CANDIDATES = {
    "river": replace(HST_CFG, lazy=False, range_margin=0.0),
    "lazy": replace(HST_CFG, lazy=True, range_margin=0.0),
    "lazy_range": replace(HST_CFG, lazy=True, range_margin=0.25),
    "lazy_range_ens": replace(HST_CFG, lazy=True, range_margin=0.25),
}
FIELDS = ["entity", "split", "candidate", "pr_auc", "f1", "precision", "recall", "mcc",
          "informedness", "oracle_f1", "warm_up_s", "score_eps", "n_nodes"]


class RobustDeviationScorer:
    """Max over features of |x - median| / MAD, with median and MAD fixed from warm-up data."""

    def fit(self, rows: list[dict]) -> "RobustDeviationScorer":
        keys = list(rows[0])
        values = np.array([[r[k] for k in keys] for r in rows], dtype=float)
        self.keys = keys
        self.median = np.median(values, axis=0)
        mad = np.median(np.abs(values - self.median), axis=0)
        self.scale = np.where(mad > 1e-9, 1.4826 * mad, values.std(axis=0) + 1e-6)
        return self

    def score(self, row: dict) -> float:
        x = np.array([row[k] for k in self.keys], dtype=float)
        return float(np.max(np.abs(x - self.median) / self.scale))


def _ecdf(reference: list[float]):
    ref = sorted(reference)
    n = len(ref)
    return lambda v: bisect.bisect_right(ref, v) / n


def run_candidate(name: str, train: list[dict], test: list[dict], labels: list[int]) -> dict:
    cfg = CANDIDATES[name]
    model = build_model(cfg)
    clamp = lambda v: float(min(max(v, 0.0), 1.0))  # noqa: E731
    split = int(len(train) * 0.8)

    t0 = time.perf_counter()
    for r in train[:split]:
        model.learn_one(r)
    calib = [clamp(model.score_one(r)) for r in train[split:]]
    for r in train[split:]:
        model.learn_one(r)
    if cfg.range_margin > 0:
        freeze_scaler(model)
    warm_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    scores = [clamp(model.score_one(r)) for r in test]
    score_eps = len(test) / (time.perf_counter() - t0)

    if name.endswith("_ens"):
        # Rank-average: map both scorers to their percentile within their own calibration
        # scores, so neither scale dominates, then calibrate the combined score the same way.
        dev = RobustDeviationScorer().fit(train[:split])
        dev_calib = [dev.score(r) for r in train[split:]]
        hst_cdf, dev_cdf = _ecdf(calib), _ecdf(dev_calib)
        calib = [(hst_cdf(a) + dev_cdf(b)) / 2 for a, b in zip(calib, dev_calib)]
        scores = [(hst_cdf(a) + dev_cdf(dev.score(r))) / 2 for a, r in zip(scores, test)]

    threshold = percentile_threshold(calib, 97)
    m = evaluate(scores, labels, threshold=threshold)
    pred = [int(s >= threshold) for s in scores]
    normal = [p for p, y in zip(pred, labels) if not y]
    hst = list(model.steps.values())[-1]
    return {
        "candidate": name,
        "pr_auc": pr_auc(scores, labels),
        "f1": m["f1"], "precision": m["precision"], "recall": m["recall"],
        "mcc": round(float(matthews_corrcoef(labels, pred)), 4),
        "informedness": round(m["recall"] - sum(normal) / max(1, len(normal)), 4),
        "oracle_f1": oracle_best_f1(scores, labels)["f1"],
        "warm_up_s": round(warm_s, 1), "score_eps": round(score_eps),
        "n_nodes": hst.n_nodes() if hasattr(hst, "n_nodes") else cfg.n_trees * (2 ** (cfg.height + 1) - 1),
    }


def summarize(path: Path) -> str:
    df = pd.read_csv(path)
    cols = ["pr_auc", "f1", "mcc", "informedness", "oracle_f1", "warm_up_s", "score_eps", "n_nodes"]
    lines = []
    for split in ("dev", "held_out"):
        sub = df[df.split == split]
        if sub.empty:
            continue
        lines.append(f"\n{split} ({sub.entity.nunique()} entities), means:")
        lines.append(sub.groupby("candidate")[cols].mean().round(4).to_string())
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entities", nargs="*", default=None)
    parser.add_argument("--candidates", nargs="*", default=list(CANDIDATES), choices=list(CANDIDATES))
    parser.add_argument("--out", default="outputs/detectors/detectors.csv")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        with open(out, newline="") as f:
            done = {(r["entity"], r["candidate"]) for r in csv.DictReader(f)}

    for entity in args.entities or discover_entities("train"):
        todo = [c for c in args.candidates if (entity, c) not in done]
        if not todo:
            continue
        train = pd.read_parquet(preprocess_entity(entity, split="train")).to_dict(orient="records")
        test = pd.read_parquet(preprocess_entity(entity, split="test")).to_dict(orient="records")
        labels = load_labels(entity)
        split = "dev" if entity.startswith("machine-1-") else "held_out"
        for name in todo:
            row = {"entity": entity, "split": split, **run_candidate(name, train, test, labels)}
            new = not out.exists()
            with open(out, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                if new:
                    w.writeheader()
                w.writerow(row)
            logger.info("%s %-14s pr_auc=%.4f f1=%.4f mcc=%.4f J=%.4f warm=%.0fs",
                        entity, name, row["pr_auc"], row["f1"], row["mcc"], row["informedness"],
                        row["warm_up_s"])
    print(summarize(out))


if __name__ == "__main__":
    main()
