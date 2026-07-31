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
model to `model_snapshots/<entity>/`. Scope is deliberately narrow — no ADWIN drift detection,
no MLflow rollback, no streaming data generator (see `CLAUDE.md` in this folder).

`--calibrate` computes a per-entity threshold from held-out normal data instead of a fixed
`--eval-threshold` — a single fixed threshold does not transfer across SMD entities (see
`RESULTS.md`). Use `sweep_hyperparams.py` and `calibrate.py` to reproduce the tuning/calibration
sweeps and `train_all.py` to evaluate a config across all 28 entities at once.

**Component 2 (streaming pipeline + dynamic model updating — not yet built):**

```bash
uv run python main.py --entity machine-1-1
```

`main.py` is still a placeholder for the teammate building the streaming ingestion pipeline and
ADWIN/MLflow-rollback logic described in `docs/Component_1_2_Technical_Guide.md` Parts 3 & 5.
`src/data_pipeline.py` and `src/mlflow_lifecycle.py` exist as docstring-only reserved stubs
marking that territory — no functions yet, just what's meant to go there and why.
