"""
Evaluate the detector and CADAL on a live Online Boutique chaos campaign.

Input: a run directory written by services/ml-backend/scripts/chaos_campaign.py, i.e.
  windows.csv        one row per injected Chaos Mesh fault: service, fault, start, end (unix s)
  telemetry.parquet  every service's live feature rows (time, service, 7 features) for the warm-up
                     hour before the campaign and the campaign itself, exported from Prometheus
  meta.json          campaign settings

For every service that received faults, the warm-up hour trains the model, and the campaign rows
are replayed through two policies with the same detector (smoothed PCA, POT threshold):
  static   frozen model
  cadal    the lifecycle as served live (accelerated pacing: one "day" = 30 min of 5 s scrapes)

A row is labelled anomalous inside a fault window on that service. Reported per (policy, service):
  detected / faults          fault windows with at least one alarm inside (window + 60 s grace)
  median time to detect      first alarm after the fault starts
  false alarms per hour      alarming rows outside every fault window (+ grace), per hour
  MCC, event recall          point-wise, as in evaluate_dynamic (stream_metrics)
  incidents learned          promotions while a fault was active or within one quarantine after
                             it (a model learning the incident as normal): should be 0

    uv run python evaluate_live_chaos.py outputs/live_chaos/<run>
"""

import argparse
import json
import statistics
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

from src.dynamic_eval import stream_metrics
from src.hst_model import detector_config
from src.lifecycle_manager import DynamicModelManager, LifecycleConfig

GRACE_S = 60
FEATURES = ("cpu_rate", "memory_used", "network_rx", "network_tx", "cpu_throttled", "restarts", "ready_ratio")


def lifecycle(policy: str, samples_per_day: int) -> LifecycleConfig:
    base = LifecycleConfig(policy=policy, threshold_method="pot")
    return replace(base.for_sampling(samples_per_day), operator_queries=False) if policy == "cadal" \
        else base.for_sampling(samples_per_day)


def run_policy(policy: str, warm: list[dict], rows: list[dict], spd: int) -> tuple[list[bool], list[dict]]:
    mgr = DynamicModelManager("svc", lifecycle(policy, spd), detector_config("pca_s5"))
    mgr.warm_up(warm)
    alarms = []
    for x in rows:
        alarms.append(bool(mgr.process(x).alarm))
    mgr.wait_for_decision(timeout=120)
    return alarms, list(mgr.decisions)


def evaluate(run: Path) -> pd.DataFrame:
    meta = json.loads((run / "meta.json").read_text())
    windows = pd.read_csv(run / "windows.csv")
    tel = pd.read_parquet(run / "telemetry.parquet")
    spd = int(round(30 * 60 / meta["scrape_seconds"]))           # live pacing: 30 min "day"
    quarantine_s = 30 * 60
    out = []
    for svc in sorted(windows.service.unique()):
        df = tel[tel.service == svc].sort_values("time")
        warm = df[(df.time >= meta["start"] - meta["warmup_minutes"] * 60) & (df.time < meta["start"])]
        live = df[df.time >= meta["start"]]
        if len(warm) < 120 or live.empty:
            print(f"skip {svc}: {len(warm)} warm-up rows, {len(live)} campaign rows")
            continue
        times = live.time.to_numpy()
        w = windows[windows.service == svc]
        labels = [int(any(s <= t <= e for s, e in zip(w.start, w.end))) for t in times]
        near = [any(s <= t <= e + GRACE_S for s, e in zip(w.start, w.end)) for t in times]
        warm_rows = warm[list(FEATURES)].to_dict(orient="records")
        live_rows = live[list(FEATURES)].to_dict(orient="records")
        for policy in ("static", "cadal"):
            alarms, decisions = run_policy(policy, warm_rows, live_rows, spd)
            m = stream_metrics(alarms, labels, None, 0.01)
            detected, delays = 0, []
            for s, e in zip(w.start, w.end):
                hits = [t for t, a in zip(times, alarms) if a and s <= t <= e + GRACE_S]
                if hits:
                    detected += 1
                    delays.append(hits[0] - s)
            outside = [a for a, n in zip(alarms, near) if not n]
            hours = len(outside) * meta["scrape_seconds"] / 3600
            learned = 0
            for d in decisions:
                if d.get("action") != "promote" or d.get("step") is None:
                    continue
                t = times[min(int(d["step"]) - 1, len(times) - 1)]
                learned += any(s <= t <= e + quarantine_s for s, e in zip(w.start, w.end))
            out.append({
                "service": svc, "policy": policy, "faults": len(w), "detected": detected,
                "median_ttd_s": round(statistics.median(delays), 1) if delays else None,
                "false_alarms_per_hour": round(sum(outside) / hours, 2) if hours else None,
                "mcc": m["mcc"], "event_recall": m["event_recall"],
                "promotions": sum(d.get("action") == "promote" for d in decisions),
                "incidents_learned": learned,
            })
    return pd.DataFrame(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    args = ap.parse_args()
    res = evaluate(args.run)
    res.to_csv(args.run / "results.csv", index=False)
    print(res.to_string(index=False))
    if not res.empty:
        tot = res.groupby("policy")[["faults", "detected", "incidents_learned"]].sum()
        print("\n" + tot.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
