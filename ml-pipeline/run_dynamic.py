"""
run_dynamic.py — Component 2: stream one SMD entity through the dynamic model updating pipeline,
with the full MLflow lifecycle (registered versions, `production` alias, archived tags, one JSON
artifact per transition) and a JSONL audit log.

This is the single-entity, production-shaped run; evaluate_dynamic.py is the multi-entity
ablation that compares policies (and skips MLflow to stay fast).

Usage:
  uv run python run_dynamic.py --entity machine-1-1 --scenario deploy
  uv run python run_dynamic.py --entity machine-2-3 --scenario silent --policy naive_rollback
  mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5001
"""

import argparse
import logging
import sys
import time
from dataclasses import replace
from pathlib import Path

import mlflow
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "datasets" / "smd"))
from preprocess import preprocess_entity  # noqa: E402

from src.change_events import ReplayChangeEventSource  # noqa: E402
from src.config import HST_CFG, PIPELINE_CFG  # noqa: E402
from src.data_pipeline import SCENARIOS, apply_injections, change_events_for, make_scenario  # noqa: E402
from src.dynamic_eval import stream_metrics  # noqa: E402
from src.evaluate import load_labels  # noqa: E402
from src.hst_state import feature_names  # noqa: E402
from src.lifecycle_manager import POLICIES, DynamicModelManager, LifecycleConfig  # noqa: E402
from src.mlflow_lifecycle import MLflowRegistry  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    datefmt="%H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("run_dynamic")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entity", default=PIPELINE_CFG.smd_entity)
    parser.add_argument("--scenario", default="deploy", choices=SCENARIOS)
    parser.add_argument("--policy", default="cadal", choices=POLICIES)
    parser.add_argument("--no-change-events", action="store_true", help="ablate the change prior")
    parser.add_argument("--audit", default=None, help="JSONL audit path (default outputs/component2/audit_<entity>.jsonl)")
    args = parser.parse_args()

    cfg = replace(LifecycleConfig(), policy=args.policy, use_change_events=not args.no_change_events)
    entity = args.entity
    audit = Path(args.audit or f"outputs/component2/audit_{entity}.jsonl")

    train = pd.read_parquet(preprocess_entity(entity, split="train")).to_dict(orient="records")
    test_df = pd.read_parquet(preprocess_entity(entity, split="test"))
    injections = make_scenario(args.scenario, test_df, entity)
    rows = apply_injections(test_df, injections).to_dict(orient="records")
    labels = load_labels(entity)

    mlflow.set_tracking_uri(PIPELINE_CFG.mlflow_tracking_uri)
    mlflow.set_experiment(f"hst_{entity}")
    with mlflow.start_run(run_name=f"{entity}_component2_{args.policy}_{args.scenario}"):
        mlflow.set_tags({"component": "2", "policy": args.policy, "scenario": args.scenario,
                         "entity_id": entity, "drift_detector": cfg.detector})
        mlflow.log_params({
            "n_trees": HST_CFG.n_trees, "height": HST_CFG.height, "window_size": HST_CFG.window_size,
            "seed": HST_CFG.seed, "calib_percentile": cfg.calib_percentile,
            "learn_gate_percentile": cfg.learn_gate_percentile, "adwin_delta": cfg.adwin_delta,
            "quarantine_with_change": cfg.quarantine_with_change,
            "quarantine_silent": cfg.quarantine_silent, "scheduled_every": cfg.scheduled_every,
            "use_change_events": cfg.use_change_events,
            "injections": "; ".join(f"start={i.start} n_features={len(i.features)} announced={i.announced}"
                                    for i in injections) or "none",
        })

        # The tree structure exists only after the first learn_one, so the MLflow registry gets
        # the feature names once warm-up has built it.
        mgr = DynamicModelManager(entity, cfg, HST_CFG,
                                  change_source=ReplayChangeEventSource(change_events_for(injections, entity)))
        mgr.model.learn_one(train[0])
        mgr.registry = MLflowRegistry(
            entity, PIPELINE_CFG.mlflow_tracking_uri, audit_path=audit,
            hst_params={"n_trees": HST_CFG.n_trees, "height": HST_CFG.height,
                        "window_size": HST_CFG.window_size, "seed": HST_CFG.seed},
            feature_names=feature_names(mgr.model),
        )
        warm = mgr.warm_up(train[1:])
        mlflow.log_metrics({"warm_up_duration_s": warm["duration_s"], "warm_up_threshold": warm["threshold"]})
        logger.info("Warm-up done in %.0fs, threshold %.4f", warm["duration_s"], warm["threshold"])

        alarms, scores = [], []
        t0 = time.perf_counter()
        for res in mgr.run(rows):
            alarms.append(res.alarm)
            scores.append(res.score)
            if res.lifecycle:
                logger.info("step %d: %s (%s) -> v%s: %s", res.step, res.lifecycle["action"],
                            res.lifecycle["verdict"], res.lifecycle["version"], res.lifecycle.get("reason", ""))
            if res.step % PIPELINE_CFG.log_every_n_steps == 0:
                window = alarms[-PIPELINE_CFG.log_every_n_steps:]
                mlflow.log_metrics({
                    "rolling_mean_score": sum(scores[-len(window):]) / len(window),
                    "rolling_alarm_rate": sum(window) / len(window),
                    "threshold": res.threshold,
                    "in_quarantine": int(res.phase == "quarantine"),
                }, step=res.step)
        duration = time.perf_counter() - t0

        drift_start = injections[0].start if injections else None
        metrics = stream_metrics(alarms, labels, drift_start, cfg.target_rate)
        mlflow.log_metrics({f"eval_{k}": v for k, v in metrics.items()
                            if isinstance(v, (int, float)) and v is not None})
        mlflow.log_metrics({"stream_duration_s": duration, "n_decisions": len(mgr.decisions),
                            "n_versions": len(mgr.registry.versions)})
        mlflow.log_artifact(str(audit), artifact_path="audit")

    logger.info("F1 %.4f (post drift %s), false alarm rate %.4f, %d decisions, %d versions, %.0fs",
                metrics["f1"], metrics.get("post_drift_f1"), metrics["fa_rate"],
                len(mgr.decisions), len(mgr.registry.versions), duration)


if __name__ == "__main__":
    main()
