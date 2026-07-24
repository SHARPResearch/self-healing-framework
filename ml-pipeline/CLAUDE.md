# ml-pipeline

Standalone Component 1-2 research pipeline (HST warm-up + streaming ADWIN drift detection),
formerly `component-1-2-pipeline/` at repo root. Full spec: `docs/Component_1_2_Technical_Guide.md`.

**Tech**: Python 3.11 (uv-managed), `river`, MLflow, pandas/pyarrow, scikit-learn.

**Status**: Component 1 (anomaly detection model) is done — `src/hst_model.py` (build/warm-up/
score/severity), `src/evaluate.py` (precision/recall/F1 against SMD labels), and `train.py` (CLI
entry point) are implemented, tested (`tests/`), and verified against the real `machine-1-1` SMD
data. Component 2 (streaming ingestion + ADWIN drift detection + MLflow rollback) is a teammate's
work and intentionally not started — `main.py` is still the uv-init placeholder, and there is no
`src/data_pipeline.py` or `src/mlflow_lifecycle.py` (those names are reserved for that work, per
the guide's Parts 3 & 5, so there's no collision when it lands).

Real results from the last verified run on `machine-1-1` (default hyperparameters: n_trees=25,
height=15, window_size=250, threshold=0.7): precision 0.51, recall 0.28, F1 0.36. Modest but
genuine — unsupervised HST with default hyperparameters on real SMD data, not tuned.

**Fixed gotcha**: the guide's Part 5 assumes `MLFLOW_TRACKING_URI=./mlruns` (a plain filesystem
store), but `mlflow>=3` rejects that by default (`MlflowException: filesystem tracking backend
... is in maintenance mode`). `src/config.py`'s default is now `sqlite:///mlflow.db` instead —
whoever builds Component 2's `mlflow_lifecycle.py` should keep using that URI, not the guide's
literal `./mlruns`.

`SMD_RAW_DIR` now points at `../datasets/smd/raw` (this repo's canonical dataset location) instead
of a local copy — don't re-duplicate the ~466MB dataset here.

**Eventually lifts into** `services/ml-backend/app/ml/` per Doc3 Phase 2-3 — this pipeline's
`HSTStreamProcessor` design already anticipates that (see the class docstring in
`docs/Component_1_2_Technical_Guide.md` Part 4).
