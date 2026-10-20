"""
evaluate_nab_dynamic.py — Component 2 on real data: static vs dynamic model updating on NAB.

The Numenta Anomaly Benchmark's real series (realAWSCloudwatch, realKnownCause, realTraffic,
realAdExchange, realTweets: 47 files with labelled anomaly windows) are real production metrics
with real, unlabelled regime changes: an AWS autoscaling misconfiguration, EC2 CPU and latency
shifts, traffic pattern changes. No drift is injected here, so whatever adaptation helps or hurts,
it does so on real behaviour.

Protocol (NAB's own): the first 15% of each series is the probationary period. It is used for the
calibrated warm-up and is not scored. The rest is streamed through every policy. Every setting
comes from the SMD defaults rescaled to the series' sampling rate
(LifecycleConfig.for_sampling, hst_window_for_sampling), with a floor of 144 samples per "day" so
that hourly series still leave the challenger a full HST window. Nothing is tuned on NAB: all 47
files are held-out data. There are no deployment logs, so the change prior never fires (cadal and
cadal_no_events coincide) and model replacement needs a change event (retrain_requires_change),
which leaves re-baselining as cadal's only repair here; cadal_retrain_free measures what that rule
costs or saves.

Metrics: NAB-style score (src/nab_scorer.py, simplified scorer: window-level TP/FN, row-level FP,
documented there), point-wise MCC and informedness (recall minus false-alarm rate), event recall.

Usage:
  uv run python evaluate_nab_dynamic.py                       # all 47 files, default detector
  uv run python evaluate_nab_dynamic.py --detector river --out-dir outputs/nab_river
"""

import argparse
import csv
import json
import logging
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_dynamic import BASE, VARIANTS, run_one, warm_up_rows
from src.dynamic_eval import stream_metrics
from src.hst_model import DETECTOR_PRESETS, detector_config
from src.lifecycle_manager import hst_window_for_sampling
from src.nab_scorer import compute_tp_fp_fn, detect_windows, nab_score

logger = logging.getLogger("evaluate_nab_dynamic")

NAB_DIR = Path(__file__).parent.parent / "datasets" / "nab" / "raw"
PROBATION = 0.15
MIN_SAMPLES_PER_DAY = 144
POLICIES = ["static", "online", "naive_rollback", "periodic", "gated", "cadal", "cadal_retrain_free"]
FIELDS = ["file", "group", "policy", "n_scored", "samples_per_day", "nab_score", "tp", "fp", "fn",
          "mcc", "informedness", "recall", "fa_rate", "event_recall", "f1", "n_promote",
          "n_rollback", "n_hold", "duration_s"]


def load_series(name: str, windows: list) -> tuple[pd.DataFrame, list[int], float]:
    df = pd.read_csv(NAB_DIR / "data" / name, parse_dates=["timestamp"])
    bounds = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in windows]
    labels = [int(any(a <= ts <= b for a, b in bounds)) for ts in df.timestamp]
    dt = df.timestamp.diff().median().total_seconds()
    return df, labels, 86400.0 / dt


def evaluate_file(name: str, windows: list, detector: str, policies: list[str]) -> list[dict]:
    df, labels, spd_raw = load_series(name, windows)
    spd = max(spd_raw, MIN_SAMPLES_PER_DAY)
    base = BASE.for_sampling(spd)
    hst_cfg = replace(detector_config(detector), window_size=hst_window_for_sampling(spd))

    # Raw values, min-max scaled by the model's own (frozen after warm-up) scaler.
    rows = [{"value": float(v)} for v in df["value"]]
    n_prob = int(len(rows) * PROBATION)
    train, stream, stream_labels = rows[:n_prob], rows[n_prob:], labels[n_prob:]
    stream_ts = list(df.timestamp.iloc[n_prob:])
    label_windows = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in windows]

    model, warm_state, calib, recent, null, ref = warm_up_rows(name, train, hst_cfg, base)
    out = []
    for policy in policies:
        cfg = replace(VARIANTS.get(policy) or _extra(policy), **_lengths(base))
        trace = {}
        t0 = time.perf_counter()
        summary, _, decisions = run_one(name, model, warm_state, calib, recent, null, stream,
                                        stream_labels, [], cfg, hst_cfg, trace, ref)
        alarms = [float(a) for a in trace["alarm"]]
        detected = detect_windows(stream_ts, alarms, 0.5)
        tp, fp, fn = compute_tp_fp_fn(detected, label_windows, stream_ts, alarms, 0.5)
        m = stream_metrics([bool(a) for a in alarms], stream_labels, None, cfg.target_rate)
        actions = [d["action"] for d in decisions]
        out.append({
            "file": name, "group": name.split("/")[0], "policy": policy, "n_scored": len(stream),
            "samples_per_day": round(spd_raw, 1),
            "nab_score": nab_score(tp, fp, fn, len(label_windows)), "tp": tp, "fp": fp, "fn": fn,
            "mcc": m["mcc"], "informedness": round(m["recall"] - (m["fa_rate"] or 0.0), 4),
            "recall": m["recall"], "fa_rate": m["fa_rate"], "event_recall": m["event_recall"],
            "f1": m["f1"], "n_promote": actions.count("promote"),
            "n_rollback": actions.count("rollback"), "n_hold": actions.count("hold"),
            "duration_s": round(time.perf_counter() - t0, 1),
        })
    return out


def _extra(policy: str):
    from evaluate_dynamic import ALL_VARIANTS
    return ALL_VARIANTS[policy]


def _lengths(base) -> dict:
    keys = ("quarantine_with_change", "quarantine_silent", "change_horizon", "cooldown",
            "scheduled_every", "scheduled_window", "periodic_window", "naive_stable_every")
    return {k: getattr(base, k) for k in keys}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--detector", default="lazy_range_ens", choices=list(DETECTOR_PRESETS))
    parser.add_argument("--policies", nargs="*", default=POLICIES)
    parser.add_argument("--files", nargs="*", default=None, help="NAB file keys; default: all real*")
    parser.add_argument("--out-dir", default="outputs/nab")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("src.mlflow_lifecycle").setLevel(logging.WARNING)

    windows = json.loads((NAB_DIR / "labels" / "combined_windows.json").read_text())
    files = args.files or sorted(k for k, v in windows.items() if k.startswith("real") and v)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "nab_runs.csv"
    done = set()
    if path.exists():
        with open(path, newline="") as f:
            done = {(r["file"], r["policy"]) for r in csv.DictReader(f)}

    for name in files:
        todo = [p for p in args.policies if (name, p) not in done]
        if not todo:
            continue
        for row in evaluate_file(name, windows[name], args.detector, todo):
            new = not path.exists()
            with open(path, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                if new:
                    w.writeheader()
                w.writerow(row)
            logger.info("%-55s %-18s nab=%s mcc=%.3f J=%.3f promote=%d hold=%d",
                        name, row["policy"], row["nab_score"], row["mcc"], row["informedness"],
                        row["n_promote"], row["n_hold"])

    df = pd.read_csv(path)
    print(df.groupby("policy")[["nab_score", "mcc", "informedness", "fa_rate", "event_recall"]]
          .agg(lambda s: round(float(np.nanmean(s)), 4)))


if __name__ == "__main__":
    main()
