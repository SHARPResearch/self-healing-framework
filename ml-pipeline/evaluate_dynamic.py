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
  cadal_frozen                                       ablation: cadal with no continuous learning

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
from src.data_pipeline import SCENARIOS, apply_injections, change_events_for, make_scenario  # noqa: E402
from src.dynamic_eval import stream_metrics  # noqa: E402
from src.evaluate import load_labels  # noqa: E402
from src.hst_model import build_model  # noqa: E402
from src.hst_state import capture  # noqa: E402
from src.lifecycle_manager import DynamicModelManager, LifecycleConfig  # noqa: E402

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
    "cadal_frozen": replace(BASE, policy="cadal", learn_gate_percentile=0.0),
}

RUN_FIELDS = [
    "entity", "scenario", "variant", "precision", "recall", "f1", "event_recall", "fa_rate",
    "post_drift_precision", "post_drift_recall", "post_drift_f1", "post_drift_fa_rate",
    "recovery_steps", "n_promote", "n_rollback", "n_hold", "n_resume", "n_versions",
    "latency_mean_ms", "latency_p50_ms", "latency_p99_ms", "transition_max_ms", "duration_s",
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


def warm_up_entity(entity_id: str):
    """One calibrated warm-up (same 80/20 split as DynamicModelManager.warm_up)."""
    train = pd.read_parquet(preprocess_entity(entity_id, split="train")).to_dict(orient="records")
    model = build_model(HST_CFG)
    split = int(len(train) * 0.8)
    for r in train[:split]:
        model.learn_one(r)
    clamp = lambda v: float(min(max(v, 0.0), 1.0))  # noqa: E731
    frozen = [clamp(model.score_one(r)) for r in train[split:]]
    prequential = []
    for r in train[split:]:
        prequential.append(clamp(model.score_one(r)))
        model.learn_one(r)
    # Same warm state for every policy; each is calibrated the way it serves (see
    # DynamicModelManager.warm_up): frozen policies on frozen scores, learning ones prequentially.
    return model, capture(model), {"frozen": frozen, "prequential": prequential}, train[-BASE.periodic_window:]


def run_one(entity_id, model, warm_state, calib, recent, rows, labels, injections, cfg):
    events = change_events_for(injections, entity_id)
    mgr = DynamicModelManager(entity_id, cfg, HST_CFG, model=model,
                              change_source=ReplayChangeEventSource(events))
    mgr.start_from(warm_state, calib["prequential" if cfg.learns_while_serving else "frozen"], recent)
    alarms, latency = [], []
    t0 = time.perf_counter()
    for x in rows:
        res = mgr.process(x)
        alarms.append(res.alarm)
        latency.append(res.latency_ms)
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
    parser.add_argument("--variants", nargs="*", default=list(VARIANTS), choices=list(VARIANTS))
    parser.add_argument("--out-dir", default="outputs/component2")
    parser.add_argument("--seed", type=int, default=0, help="drift injection seed")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("src.mlflow_lifecycle").setLevel(logging.WARNING)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs_csv, curves_csv, decisions_path = out / "runs.csv", out / "f1_curves.csv", out / "decisions.jsonl"
    done = _done_keys(runs_csv)
    entities = args.entities or discover_entities("train")

    for entity_id in entities:
        todo = [(s, v) for s in args.scenarios for v in args.variants if (entity_id, s, v) not in done]
        if not todo:
            continue
        t = time.perf_counter()
        model, warm_state, calib, recent = warm_up_entity(entity_id)
        logger.info("[%s] warm-up %.0fs, %d runs to do", entity_id, time.perf_counter() - t, len(todo))
        test_df = pd.read_parquet(preprocess_entity(entity_id, split="test"))
        labels = load_labels(entity_id)

        for scenario in args.scenarios:
            injections = make_scenario(scenario, test_df, entity_id, seed=args.seed)
            rows = apply_injections(test_df, injections).to_dict(orient="records")
            for variant in args.variants:
                if (entity_id, scenario, variant) in done:
                    continue
                summary, curve, decisions = run_one(
                    entity_id, model, warm_state, calib, recent, rows, labels, injections, VARIANTS[variant])
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
