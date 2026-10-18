"""
evaluate_dynamic.py — Component 2 evaluation: lifecycle policies x drift scenarios x SMD entities.

For every entity: one calibrated warm-up on the train split (shared by every run through a
sparse snapshot, see src/hst_state.py), then for every scenario (src/data_pipeline.SCENARIOS)
and policy variant, stream the (possibly drift-injected) test split through a
DynamicModelManager and score its alarms against the SMD labels (src/dynamic_eval.py).

Policy variants:
  static, online, naive_rollback, periodic, gated   baselines, see src/lifecycle_manager.py
  cadal                                              proposed method
  cadal_no_events                                    ablation: cadal without the change prior
  cadal_online                                       ablation: cadal with gated continuous learning
  cadal_retrain_only                                 ablation: cadal without re-baselining
  cadal_retrain_free                                 ablation: cadal may retrain without a change event
  cadal_page_hinkley, cadal_kswin                    ablation: score drift detector (not in the default
                                                     sweep, run with --variants)

Outputs (outputs/component2/ by default), appended per run so an interrupted sweep resumes:
  runs.csv         one row per (entity, scenario, variant)
  f1_curves.csv    F1 per tenth of the stream, per run
  decisions.jsonl  every lifecycle decision with its attribution evidence

Usage:
  uv run python evaluate_dynamic.py                                  # everything, serial
  uv run python evaluate_dynamic.py --entities machine-1-1 --variants static cadal
"""

import argparse
import csv
import json
import logging
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "datasets" / "smd"))
from preprocess import discover_entities, preprocess_entity  # noqa: E402

from src.change_events import ReplayChangeEventSource  # noqa: E402
from src.config import HST_CFG  # noqa: E402
from src.drift_attribution import AttributionConfig  # noqa: E402
from src.data_pipeline import SCENARIOS, apply_injections, change_events_for, make_scenario  # noqa: E402
from src.dynamic_eval import stream_metrics  # noqa: E402
from src.evaluate import load_labels  # noqa: E402
from src.hst_state import capture  # noqa: E402
from src.hst_model import DETECTOR_PRESETS, build_model, detector_config, freeze_scaler  # noqa: E402
from src.lifecycle_manager import (  # noqa: E402
    DynamicModelManager, LifecycleConfig, attribution_null, prepare_calibration, robust_stats,
)

logger = logging.getLogger("evaluate_dynamic")

BASE = LifecycleConfig()
VARIANTS = {
    "static": replace(BASE, policy="static"),
    "online": replace(BASE, policy="online"),
    "naive_rollback": replace(BASE, policy="naive_rollback"),
    "periodic": replace(BASE, policy="periodic"),
    "gated": replace(BASE, policy="gated"),
    "cadal": replace(BASE, policy="cadal"),
    "cadal_no_events": replace(BASE, policy="cadal", use_change_events=False),
    "cadal_online": replace(BASE, policy="cadal", learn_gate_percentile=75.0),
    "cadal_retrain_only": replace(BASE, policy="cadal", rebaseline=False),
    "cadal_retrain_free": replace(BASE, policy="cadal", attribution=AttributionConfig(retrain_requires_change=False)),
    "cadal_hitl": replace(BASE, policy="cadal", operator_queries=True),
    "cadal_hitl_noisy": replace(BASE, policy="cadal", operator_queries=True),
}
DETECTOR_VARIANTS = {
    "cadal_page_hinkley": replace(BASE, policy="cadal", detector="page_hinkley"),
    "cadal_kswin": replace(BASE, policy="cadal", detector="kswin"),
}
ALL_VARIANTS = {**VARIANTS, **DETECTOR_VARIANTS}

# Simulated operator for the CADAL-HITL variants: how often it answers wrongly.
OPERATOR_ERROR = {"cadal_hitl": 0.0, "cadal_hitl_noisy": 0.2}
OPERATOR_DELAY = 60          # events between a query and its answer (an hour at SMD's rate)
OPERATOR_INCIDENT_SHARE = 0.1


class SimulatedOperator:
    """
    Stands in for the on-call engineer answering CADAL's "new normal or incident?" queries.

    Looks only at the ground-truth labels of the quarantine tail the query was raised on (the
    events the engineer would be looking at) and answers "incident" if at least 10% of them are
    labelled anomalous, else "new_normal"; flips its answer with probability `error_rate`. Labels
    are used for nothing else, and every query is counted, so the evaluation measures detection
    gained per question asked.
    """

    def __init__(self, labels: list[int], error_rate: float = 0.0, delay: int = OPERATOR_DELAY,
                 seed: int = 0):
        import random as _random
        self.labels, self.error_rate, self.delay = labels, error_rate, delay
        self.rng = _random.Random(seed)
        self.scheduled: dict[str, int] = {}
        self.asked = self.answered = self.said_new_normal = 0

    def step(self, mgr) -> None:
        for q in mgr.open_queries:
            if q["query_id"] not in self.scheduled:
                self.scheduled[q["query_id"]] = mgr.step + self.delay
                self.asked += 1
        for query_id, due in list(self.scheduled.items()):
            q = mgr.queries.get(query_id)
            if q is None or q["status"] != "open":
                self.scheduled.pop(query_id)
                continue
            if mgr.step >= due and mgr._pending is None:
                n_tail = q["evidence"].get("n_tail") or 100
                end = q["created_step"]                      # steps are 1-based row indices
                tail = self.labels[max(0, end - n_tail):end]
                incident = (sum(tail) / max(1, len(tail))) >= OPERATOR_INCIDENT_SHARE
                if self.rng.random() < self.error_rate:
                    incident = not incident
                answer = "incident" if incident else "new_normal"
                self.said_new_normal += answer == "new_normal"
                mgr.answer_query(query_id, answer, operator="simulated")
                self.answered += 1
                self.scheduled.pop(query_id)


RUN_FIELDS = [
    "entity", "scenario", "variant", "precision", "recall", "f1", "mcc", "event_recall", "fa_rate",
    "post_drift_precision", "post_drift_recall", "post_drift_f1", "post_drift_mcc", "post_drift_fa_rate",
    "recovery_steps", "n_promote", "n_rollback", "n_hold", "n_resume", "n_versions",
    "latency_mean_ms", "latency_p50_ms", "latency_p99_ms", "transition_max_ms", "duration_s",
    "n_queries", "n_answered_new_normal",
]


def _done_keys(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    with open(path, newline="") as f:
        return {(r["entity"], r["scenario"], r["variant"]) for r in csv.DictReader(f)}


def _append(path: Path, fields: list[str], row: dict) -> None:
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow(row)


def warm_up_entity(entity_id: str, hst_cfg=HST_CFG, base: LifecycleConfig = BASE):
    """One calibrated warm-up on an SMD entity's train split."""
    train = pd.read_parquet(preprocess_entity(entity_id, split="train")).to_dict(orient="records")
    return warm_up_rows(entity_id, train, hst_cfg, base)


def warm_up_rows(entity_id: str, train: list[dict], hst_cfg=HST_CFG, base: LifecycleConfig = BASE):
    """
    One calibrated warm-up (same 80/20 split as DynamicModelManager.warm_up), shared by every
    policy run on this stream. `base` sets the quarantine lengths the attribution null is
    computed for, so it must match the lifecycle configs the runs will use.
    """
    model = build_model(hst_cfg)
    split = int(len(train) * 0.8)
    for r in train[:split]:
        model.learn_one(r)
    prepare_calibration(model, train[:split], train[split:])
    clamp = lambda v: float(min(max(v, 0.0), 1.0))  # noqa: E731
    frozen = [clamp(model.score_one(r)) for r in train[split:]]
    prequential = []
    for r in train[split:]:
        prequential.append(clamp(model.score_one(r)))
        model.learn_one(r)
    freeze_scaler(model)
    # Same warm state for every policy; each is calibrated the way it serves (see
    # DynamicModelManager.warm_up): frozen policies on frozen scores, learning ones prequentially.
    # The attribution null depends only on the quarantine lengths, so cadal variants share it.
    null = attribution_null(DynamicModelManager(entity_id, base, hst_cfg, model=model), train)
    ref = robust_stats(train[:split])
    return (model, capture(model), {"frozen": frozen, "prequential": prequential},
            train[-base.periodic_window:], null, ref)


def run_one(entity_id, model, warm_state, calib, recent, null, rows, labels, injections, cfg,
            hst_cfg=HST_CFG, trace: dict | None = None, ref: dict | None = None,
            operator_error: float | None = None):
    events = change_events_for(injections, entity_id)
    mgr = DynamicModelManager(entity_id, cfg, hst_cfg, model=model,
                              change_source=ReplayChangeEventSource(events))
    mgr.start_from(warm_state, calib["prequential" if cfg.learns_while_serving else "frozen"], recent,
                   null if cfg.policy == "cadal" else None, ref_stats=ref)
    alarms, latency, scores, versions, thresholds = [], [], [], [], []
    operator = (SimulatedOperator(labels, operator_error)
                if cfg.operator_queries and operator_error is not None else None)
    t0 = time.perf_counter()
    for x in rows:
        res = mgr.process(x)
        if operator is not None:
            operator.step(mgr)
        alarms.append(res.alarm)
        latency.append(res.latency_ms)
        if trace is not None:
            scores.append(res.score)
            versions.append(res.version)
            thresholds.append(res.threshold)
    if trace is not None:
        trace.update(alarm=np.array(alarms), score=np.array(scores), version=np.array(versions),
                     threshold=np.array(thresholds), label=np.array(labels))
    duration = time.perf_counter() - t0
    drift_start = injections[0].start if injections else None
    metrics = stream_metrics(alarms, labels, drift_start, cfg.target_rate)
    actions = [d["action"] for d in mgr.decisions]
    lat = np.array(latency)
    summary = {
        **{k: v for k, v in metrics.items() if k != "f1_curve"},
        "n_promote": actions.count("promote"), "n_rollback": actions.count("rollback"),
        "n_hold": actions.count("hold"), "n_resume": actions.count("resume"),
        "n_versions": len(mgr.registry.versions),
        "n_queries": operator.asked if operator else 0,
        "n_answered_new_normal": operator.said_new_normal if operator else 0,
        "latency_mean_ms": round(float(lat.mean()), 4),
        "latency_p50_ms": round(float(np.percentile(lat, 50)), 4),
        "latency_p99_ms": round(float(np.percentile(lat, 99)), 4),
        "transition_max_ms": round(max(mgr.transition_ms), 1) if mgr.transition_ms else 0.0,
        "duration_s": round(duration, 1),
    }
    return summary, metrics["f1_curve"], mgr.decisions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entities", nargs="*", default=None, help="default: all SMD entities")
    parser.add_argument("--scenarios", nargs="*", default=list(SCENARIOS), choices=SCENARIOS)
    parser.add_argument("--variants", nargs="*", default=list(VARIANTS), choices=list(ALL_VARIANTS))
    parser.add_argument("--out-dir", default="outputs/component2")
    parser.add_argument("--seed", type=int, default=0, help="drift injection seed")
    parser.add_argument("--shard", default="0/1", help="i/n: run every n-th entity starting at i (parallel workers)")
    parser.add_argument("--detector", default="river", choices=list(DETECTOR_PRESETS),
                        help="Component 1 detector preset (src/hst_model.DETECTOR_PRESETS)")
    parser.add_argument("--threshold", default="percentile", choices=["percentile", "pot"],
                        help="calibration rule for every policy (LifecycleConfig.threshold_method)")
    parser.add_argument("--trace", action="store_true",
                        help="save per-step score / alarm / version / threshold to <out-dir>/traces/")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("src.mlflow_lifecycle").setLevel(logging.WARNING)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs_csv, curves_csv, decisions_path = out / "runs.csv", out / "f1_curves.csv", out / "decisions.jsonl"
    done = _done_keys(runs_csv)
    hst_cfg = detector_config(args.detector)
    base = replace(BASE, threshold_method=args.threshold)
    entities = args.entities or discover_entities("train")
    shard, n_shards = (int(v) for v in args.shard.split("/"))
    entities = entities[shard::n_shards]

    for entity_id in entities:
        todo = [(s, v) for s in args.scenarios for v in args.variants if (entity_id, s, v) not in done]
        if not todo:
            continue
        t = time.perf_counter()
        model, warm_state, calib, recent, null, ref = warm_up_entity(entity_id, hst_cfg, base)
        logger.info("[%s] warm-up %.0fs, %d runs to do", entity_id, time.perf_counter() - t, len(todo))
        test_df = pd.read_parquet(preprocess_entity(entity_id, split="test"))
        labels = load_labels(entity_id)

        for scenario in args.scenarios:
            injections = make_scenario(scenario, test_df, entity_id, seed=args.seed)
            rows = apply_injections(test_df, injections).to_dict(orient="records")
            for variant in args.variants:
                if (entity_id, scenario, variant) in done:
                    continue
                trace = {} if args.trace else None
                summary, curve, decisions = run_one(
                    entity_id, model, warm_state, calib, recent, null, rows, labels, injections,
                    replace(ALL_VARIANTS[variant], threshold_method=args.threshold), hst_cfg, trace, ref,
                    OPERATOR_ERROR.get(variant))
                if trace:
                    (out / "traces").mkdir(exist_ok=True)
                    np.savez_compressed(out / "traces" / f"{entity_id}_{scenario}_{variant}.npz", **trace)
                key = {"entity": entity_id, "scenario": scenario, "variant": variant}
                _append(runs_csv, RUN_FIELDS, {**key, **summary})
                for i, f1 in enumerate(curve):
                    _append(curves_csv, ["entity", "scenario", "variant", "slice", "f1"], {**key, "slice": i, "f1": f1})
                with open(decisions_path, "a") as f:
                    for d in decisions:
                        f.write(json.dumps({**key, **d}, default=str) + "\n")
                logger.info("[%s] %-11s %-15s f1=%.4f post=%s fa=%.4f decisions=%d %.0fs",
                            entity_id, scenario, variant, summary["f1"],
                            summary.get("post_drift_f1"), summary["fa_rate"], len(decisions),
                            summary["duration_s"])


if __name__ == "__main__":
    main()
