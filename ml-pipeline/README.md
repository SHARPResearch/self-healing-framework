# ml-pipeline

Standalone HST anomaly-detection + ADWIN drift-detection research pipeline (Component 1
extension + Component 2), formerly `component-1-2-pipeline/`. See
`docs/Component_1_2_Technical_Guide.md` for the full walkthrough and
`docs/Doc3_Execution_Guide.md` Phase 2 for how this folds into the FastAPI monorepo later.

Raw SMD data lives in `../datasets/smd/raw/` (not duplicated here) — see `.env`'s `SMD_RAW_DIR`.

## Quick start

**Component 1 (anomaly detection model — train + evaluate, done):**

```bash
uv sync
uv run python train.py --entity machine-1-1 --calibrate   # recommended, see RESULTS.md
uv run python train.py --entity machine-1-1               # fixed threshold, single entity only
uv run pytest tests/ -v
mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5001   # view runs
```

`train.py` warms up river's HalfSpaceTrees on the training split, scores the held-out test
split (model frozen, no further learning), evaluates against SMD ground truth, and saves the
model to `model_snapshots/<entity>/`. Scope is deliberately narrow: drift handling and the model
lifecycle are Component 2, below.

`--calibrate` computes a per-entity threshold from held-out normal data instead of a fixed
`--eval-threshold` — a single fixed threshold does not transfer across SMD entities (see
`RESULTS.md`). Use `sweep_hyperparams.py` and `calibrate.py` to reproduce the tuning/calibration
sweeps and `train_all.py` to evaluate a config across all 28 entities at once.

**Component 2 (dynamic model updating with concept drift detection, CADAL):**

```bash
# One entity, production-shaped: MLflow registered versions, `production` alias, audit JSONL
# (defaults to the final configuration: smoothed PCA detector, POT thresholds)
uv run python run_dynamic.py --entity machine-1-1 --scenario deploy
uv run python run_dynamic.py --entity machine-1-1 --scenario silent --policy naive_rollback

# The ablation: 8 policies x 4 drift scenarios x 28 entities (resumable, ~2 workers x 4.5 h)
uv run python evaluate_dynamic.py --shard 0/2 --out-dir outputs/component2/shard0
uv run python evaluate_dynamic.py --shard 1/2 --out-dir outputs/component2/shard1
uv run python summarize_dynamic.py --out-dir outputs/component2   # tables + Wilcoxon tests

# Final configuration sweep, real data, detectors and scalability (see RESULTS_COMPONENT2.md)
uv run python evaluate_dynamic.py --shard 0/2 --detector pca_s5 --threshold pot --out-dir outputs/final/smd_pca_pot/shard0
uv run python evaluate_nab_dynamic.py                 # 46 real NAB series
bash ../datasets/rcaeval/download.sh && uv run python evaluate_rcaeval.py --threshold pot
uv run python compare_detectors.py                    # Component 1 detector comparison
uv run python benchmark_scalability.py                # memory, latency, horizontal scaling
```

For the panel: `../docs/Component_2_Panel_Response.md` answers the scalability and
dynamic-vs-static comments with the measured numbers.

Design and research positioning: `../docs/Component_2_Dynamic_Model_Updating.md`. Results:
`RESULTS_COMPONENT2.md`. In short, a detected shift is *attributed* (incident, concept drift,
model decay or no change) from label-free evidence gathered in a quarantine before any lifecycle
action is taken, and every model+threshold the detector serves is a validated, versioned and
audited transition.

| Module | What it does |
|---|---|
| `src/lifecycle_manager.py` | `DynamicModelManager`: triggers, quarantine, challenger, promote / hold / rollback, every policy used in the ablation |
| `src/drift_attribution.py` | pure attribution rules (verdict → action) with per-entity null floors |
| `src/drift_detectors.py` | directional score drift monitor (ADWIN default, Page-Hinkley, KSWIN) |
| `src/change_events.py` | change events: replay source, Kubernetes Deployment watcher |
| `src/hst_state.py` | structure-sharing sparse HST snapshots (~13 KB, ~37 ms restore vs 71 MB / ~6 s pickle) |
| `src/detectors.py` | Component 1 v3: PCA reconstruction-error detector, EWMA score smoothing |
| `src/lazy_hst.py` | river's Half-Space Trees built on demand (0.1 MB instead of 370 MB per model) |
| `src/ensemble.py` | rank ensemble of HST and a robust per-feature deviation score |
| `src/mlflow_lifecycle.py` | versioned registry: in-memory + MLflow (aliases, archived tags, transition artifacts, `sync_production` for replicas) |
| `src/hst_pyfunc.py` | registered versions load with `mlflow.pyfunc.load_model` |
| `src/publishers.py` | lifecycle events to Redis `ws:anomaly_broadcast` / `anomaly_events` |
| `src/data_pipeline.py` | SMD streaming + reproducible deploy / silent / no-op drift injection |
| `src/dynamic_eval.py` | post-hoc metrics: F1, MCC, event recall, false-alarm rate, recovery time |

`main.py` is the separate live Prometheus loop (online-boutique on Kubernetes) from PR #20; it
still uses `HSTStreamProcessor` and does not go through the lifecycle manager yet.
