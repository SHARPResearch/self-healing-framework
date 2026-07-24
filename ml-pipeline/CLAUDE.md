# ml-pipeline

Standalone Component 1-2 research pipeline (HST warm-up + streaming ADWIN drift detection),
formerly `component-1-2-pipeline/` at repo root. Full spec: `docs/Component_1_2_Technical_Guide.md`.

**Tech**: Python 3.11 (uv-managed), `river`, MLflow, pandas/pyarrow, scikit-learn.

**Status**: environment + config scaffold only. `src/config.py` (HST/ADWIN/pipeline dataclasses)
exists and works; `main.py` is still the uv-init placeholder. `src/data_pipeline.py`,
`src/hst_model.py`, `src/mlflow_lifecycle.py` from the guide's Parts 3-5 are not yet written.

**Known gotcha for whoever implements this next**: the guide's Part 5 assumes
`MLFLOW_TRACKING_URI=./mlruns` (a plain filesystem store), but `mlflow>=3` rejects the filesystem
backend by default (`MlflowException: filesystem tracking backend ... is in maintenance mode`).
Use `sqlite:///mlflow.db` instead, or set `MLFLOW_ALLOW_FILE_STORE=true` to keep the guide's
literal setting.

`SMD_RAW_DIR` now points at `../datasets/smd/raw` (this repo's canonical dataset location) instead
of a local copy — don't re-duplicate the ~466MB dataset here.

**Eventually lifts into** `services/ml-backend/app/ml/` per Doc3 Phase 2-3 — this pipeline's
`HSTStreamProcessor` design already anticipates that (see the class docstring in
`docs/Component_1_2_Technical_Guide.md` Part 4).
