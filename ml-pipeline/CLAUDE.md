# ml-pipeline

Standalone Component 1-2 research pipeline (HST warm-up + streaming ADWIN drift detection),
formerly `component-1-2-pipeline/` at repo root. Full spec: `docs/Component_1_2_Technical_Guide.md`.

**Tech**: Python 3.11 (uv-managed), `river`, MLflow, pandas/pyarrow, scikit-learn.

**Status**: Component 1 (anomaly detection model) is done and tuned — `src/hst_model.py`
(build/warm-up/score/severity), `src/evaluate.py` (precision/recall/F1), `src/pipeline.py`
(shared `train_and_evaluate()` / `warm_up_and_score()`, used by `train.py`,
`sweep_hyperparams.py`, and `train_all.py`) are implemented and tested (`tests/`). Component 2
(streaming ingestion + ADWIN drift detection + MLflow rollback) is a teammate's work and
intentionally not started — `main.py` is still the uv-init placeholder, and there is no
`src/data_pipeline.py` or `src/mlflow_lifecycle.py` (those names are reserved for that work).

**Tuning done, see `RESULTS.md` for full numbers and honest caveats**: threshold swept
(0.7 guide default -> 0.4, best F1 on `machine-1-1`), hyperparameters swept one-at-a-time
(baseline `n_trees=25, height=15, window_size=250` already won every comparison, no `.env`
change needed there), and run across all 28 SMD entities. The important finding from the
all-entities run: `machine-1-1`'s F1 (0.5663) is nearly 5x the 28-entity mean (0.1195) --
it was the best case, not representative, because a single global threshold does not transfer
across machines with different HST score distributions. `EVAL_THRESHOLD=0.4` is a documented
known weak point, not a silently-swept-under one. Per-entity threshold calibration is the
concrete next step, left out of this pass's scope.

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
