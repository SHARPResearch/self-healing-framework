# ml-pipeline

Standalone HST anomaly-detection + ADWIN drift-detection research pipeline (Component 1
extension + Component 2), formerly `component-1-2-pipeline/`. See
`docs/Component_1_2_Technical_Guide.md` for the full walkthrough and
`docs/Doc3_Execution_Guide.md` Phase 2 for how this folds into the FastAPI monorepo later.

Raw SMD data lives in `../datasets/smd/raw/` (not duplicated here) — see `.env`'s `SMD_RAW_DIR`.

## Quick start

```bash
uv sync
mlflow ui --backend-store-uri ./mlruns --port 5001   # separate terminal
uv run python main.py --entity machine-1-1
```
