"""
benchmark_scalability.py — Component 2 scalability: how many services one ml-backend process can
serve, and what a replica costs to bring up to date.

Measured on SMD machine-1-1 telemetry (38 features, one sample per minute), one
DynamicModelManager per simulated service (each its own model objects, registry, drift monitor):

  memory     Python heap per service (tracemalloc) for N services, lazy ensemble detector vs
             river's eager HalfSpaceTrees (Component 1 as shipped).
  serving    N services streamed round-robin, each receiving a deployment change event so that
             every service also goes through a full quarantine and decision: events/s, per-event
             latency p50/p99/max, and how long the serving loop was blocked by decisions, with
             synchronous vs asynchronous (background) quarantine evaluation.
  storage    snapshot size per registered version.
  replicas   time for a second registry/model (a replica) to pick up a new production version
             through MLflow (sync_production + apply), the FR5 path.

Usage:
  uv run python benchmark_scalability.py                       # sizes 1 10 50 100
  uv run python benchmark_scalability.py --sizes 1 10 --events 2500
"""

import argparse
import json
import random
import statistics
import sys
import tempfile
import time
import tracemalloc
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "datasets" / "smd"))
from preprocess import preprocess_entity  # noqa: E402

from src.change_events import ChangeEvent, ReplayChangeEventSource  # noqa: E402
from src.hst_model import build_model, detector_config  # noqa: E402
from src.hst_state import apply, capture, feature_names, materialize  # noqa: E402
from src.lifecycle_manager import DynamicModelManager, LifecycleConfig  # noqa: E402

ENTITY = "machine-1-1"


def _data():
    train = pd.read_parquet(preprocess_entity(ENTITY, split="train")).to_dict(orient="records")
    test = pd.read_parquet(preprocess_entity(ENTITY, split="test")).to_dict(orient="records")
    return train, test


def warm_templates(train, hst_cfg, cfg, k=4):
    """k independently warmed-up models (different training windows) to clone services from."""
    templates = []
    for i in range(k):
        rows = train[i * 4000:(i * 4000) + 8000]
        mgr = DynamicModelManager(f"template-{i}", cfg, hst_cfg)
        mgr.warm_up(rows)
        templates.append({
            "state": capture(mgr.model), "features": feature_names(mgr.model),
            "calib": [mgr.threshold], "ref": mgr.ref_stats, "null": mgr.attribution_null,
            "threshold": mgr.threshold, "gate": mgr.learn_gate,
        })
    return templates


def make_service(i, template, hst_cfg, cfg, events):
    mgr = DynamicModelManager(f"svc-{i}", cfg, hst_cfg, change_source=ReplayChangeEventSource(events))
    materialize(mgr.model, template["features"])
    apply(mgr.model, template["state"])
    # start_from recalibrates from scores; reuse the template's threshold directly instead.
    mgr.start_from(None, [template["threshold"]] * 10, [], template["null"], ref_stats=template["ref"])
    mgr.threshold, mgr.learn_gate = template["threshold"], template["gate"]
    return mgr


def memory_per_service(n, templates, hst_cfg, cfg):
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    services = [make_service(i, templates[i % len(templates)], hst_cfg, cfg, []) for i in range(n)]
    used = tracemalloc.get_traced_memory()[0] - before
    tracemalloc.stop()
    del services
    return used / n


def river_memory_per_model(train, n=2):
    cfg = detector_config("river")
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    models = []
    for _ in range(n):
        m = build_model(cfg)
        for r in train[:1000]:
            m.learn_one(r)
        models.append(m)
    used = tracemalloc.get_traced_memory()[0] - before
    tracemalloc.stop()
    return used / n


def serving(n, templates, test, hst_cfg, cfg, events_per_service, change_at):
    services = [
        make_service(i, templates[i % len(templates)], hst_cfg, cfg,
                     [ChangeEvent(f"svc-{i}", "deployment", step=change_at)])
        for i in range(n)
    ]
    offsets = [random.Random(i).randrange(0, len(test) - events_per_service) for i in range(n)]
    latencies = []
    t0 = time.perf_counter()
    for step in range(events_per_service):
        for svc, off in zip(services, offsets):
            x = test[off + step]
            t = time.perf_counter()
            svc.process(x)
            latencies.append((time.perf_counter() - t) * 1000)
    wall = time.perf_counter() - t0
    for svc in services:
        svc.wait_for_decision(timeout=600)
    blocked = [ms for s in services for ms in s.transition_ms]
    decided = [ms for s in services for ms in s.decision_ms]
    lat = np.array(latencies)
    return {
        "services": n, "events": int(lat.size), "events_per_s": round(lat.size / wall),
        "latency_p50_ms": round(float(np.percentile(lat, 50)), 3),
        "latency_p99_ms": round(float(np.percentile(lat, 99)), 3),
        "latency_max_ms": round(float(lat.max()), 1),
        "decisions": len(decided),
        "decision_eval_ms_median": round(statistics.median(decided), 1) if decided else None,
        "serving_blocked_ms_max": round(max(blocked), 1) if blocked else None,
    }


def snapshot_bytes(templates):
    from src.hst_state import HSTState
    return [len(HSTState.to_bytes(t["state"])) for t in templates]


def replica_sync(train, hst_cfg, cfg, repeats=5):
    import mlflow
    from src.mlflow_lifecycle import MLflowRegistry

    # ignore_cleanup_errors: on Windows MLflow keeps the SQLite file open after the run.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        uri = f"sqlite:///{Path(tmp, 'mlflow.db').as_posix()}"
        mlflow.set_tracking_uri(uri)
        exp = mlflow.create_experiment("scalability", artifact_location=Path(tmp, "artifacts").as_uri())
        mlflow.set_experiment(experiment_id=exp)
        primary = DynamicModelManager("svc-sync", cfg, hst_cfg)
        primary.model.learn_one(train[0])
        params = {"n_trees": hst_cfg.n_trees, "height": hst_cfg.height,
                  "window_size": hst_cfg.window_size, "seed": hst_cfg.seed}
        timings = []
        with mlflow.start_run():
            primary.registry = MLflowRegistry("svc-sync", uri, hst_params=params,
                                              feature_names=feature_names(primary.model))
            primary.warm_up(train[1:6001])
            replica_registry = MLflowRegistry("svc-sync", uri)
            replica = build_model(hst_cfg)
            materialize(replica, feature_names(primary.model))
            for _ in range(repeats):
                t = time.perf_counter()
                _, state, _ = replica_registry.sync_production()
                apply(replica, state)
                timings.append((time.perf_counter() - t) * 1000)
        return {"replica_sync_ms_median": round(statistics.median(timings), 1),
                "replica_sync_ms_max": round(max(timings), 1)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sizes", nargs="*", type=int, default=[1, 10, 50, 100])
    parser.add_argument("--events", type=int, default=2400, help="events per service in the serving test")
    parser.add_argument("--detector", default="lazy_range_ens")
    parser.add_argument("--out", default="outputs/scalability/scalability.json")
    args = parser.parse_args()

    train, test = _data()
    hst_cfg = detector_config(args.detector)
    # The null needs 8 stationarity tests per service at warm-up; 2 keeps the benchmark short and
    # does not change serving cost (it is only computed once, at warm-up).
    sync_cfg = replace(LifecycleConfig(policy="cadal"), null_windows=2)
    async_cfg = replace(sync_cfg, async_decisions=True)
    templates = warm_templates(train, hst_cfg, sync_cfg)

    result = {"detector": args.detector, "entity": ENTITY, "memory": [], "serving_sync": [],
              "serving_async": []}
    result["river_bytes_per_model"] = round(river_memory_per_model(train))
    for n in args.sizes:
        result["memory"].append({"services": n,
                                 "bytes_per_service": round(memory_per_service(n, templates, hst_cfg, sync_cfg))})
        print("memory", result["memory"][-1], flush=True)
    for n in args.sizes:
        for key, cfg in (("serving_sync", sync_cfg), ("serving_async", async_cfg)):
            row = serving(n, templates, test, hst_cfg, cfg, args.events, change_at=200)
            result[key].append(row)
            print(key, row, flush=True)
    result["snapshot_bytes"] = snapshot_bytes(templates)
    result.update(replica_sync(train, hst_cfg, sync_cfg))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
