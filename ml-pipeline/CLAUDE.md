# ml-pipeline

Standalone Component 1-2 research pipeline (HST warm-up + streaming ADWIN drift detection),
formerly `component-1-2-pipeline/` at repo root. Full spec: `docs/Component_1_2_Technical_Guide.md`.

**Tech**: Python 3.11 (uv-managed), `river`, MLflow, pandas/pyarrow, scikit-learn.

**Status**: Component 1 (anomaly detection model) is done, tuned, and calibrated —
`src/hst_model.py` (build/warm-up/score/severity), `src/evaluate.py` (precision/recall/F1,
PR-AUC, percentile threshold, oracle best F1), `src/pipeline.py` (shared `train_and_evaluate()`
/ `warm_up_and_score()` / `warm_up_calibrate_and_score()`, used by `train.py`,
`sweep_hyperparams.py`, `train_all.py`, and `calibrate.py`) are implemented and tested (`tests/`).
Component 2 (streaming ingestion + ADWIN drift detection + MLflow rollback) is a teammate's work
and intentionally not started — `main.py` is still the uv-init placeholder, and
`src/data_pipeline.py` / `src/mlflow_lifecycle.py` exist only as reserved, docstring-only stub
files (no functions, no classes) marking out that territory so there's no filename collision
when the real implementation lands. See each file's docstring for what it's meant to contain and
which guide part it maps to.

**Tuning + calibration done, see `RESULTS.md` for full numbers and honest caveats**: threshold
swept (0.7 guide default -> 0.4), hyperparameters swept one-at-a-time (baseline
`n_trees=25, height=15, window_size=250` already won every comparison, no `.env` change needed
there), run across all 28 SMD entities (found `machine-1-1`'s F1 was the best case, not
representative -- a fixed global threshold does not transfer across entities), and then fixed
with per-entity percentile-based threshold calibration (`calibrate.py`,
`train.py --calibrate`). Calibration nearly doubles mean F1 (0.1195 -> 0.2097 at percentile
99.5) but does not fully close the gap to a non-deployable oracle upper bound (0.3505), and no
single percentile is best for every entity -- documented as a real, ongoing limitation, not
silently smoothed over. `--calibrate`'s default percentile (97) is a judgment call, not the
single best mean or median; re-tune it if the entity mix changes.

`sweep_hyperparams.py` and `train_all.py` run fully serially (`max_workers=1`), not in
parallel, even though both are embarrassingly parallel workloads -- this machine does not have
enough genuinely free RAM at any given time (other applications already use most of the 16GB
installed) to run more than one HalfSpaceTrees training at once without risking exhausting
memory. Also watch out for `height`: HalfSpaceTrees builds `2^height` nodes per tree up front,
so it is exponential in cost, not linear -- `height=18` alone took 815 seconds versus the
baseline `height=15`'s 105.

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
