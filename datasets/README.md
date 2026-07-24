# datasets

Dataset download + preprocessing scripts. **The raw data itself is gitignored** — fetch it with
the scripts below, don't commit it (see `docs/Doc2_GitHub_Monorepo_Structure.md`).

- `smd/` — Server Machine Dataset (primary training data, Doc1 §9). `./download.sh` fetches it
  from the OmniAnomaly repo into `smd/raw/{train,test,test_label}/`; `preprocess.py` standardises
  it to the canonical feature schema and writes `smd/processed/{entity_id}_{split}.parquet`.
- `nab/` — Numenta Anomaly Benchmark (evaluation harness, Doc1 §9). Not yet scaffolded; follows
  the same `download.sh`/`preprocess.py`/`.gitignore` pattern as `smd/` once needed.
- `schemas/feature_vector.json` — canonical feature schema shared across services.

**Note**: a full copy of the SMD raw data already exists on disk in this repo (checked out from
git history, ~466MB across 3 early commits). Going forward it is gitignored so it won't be
re-committed, but the historical size in `.git` itself hasn't been reduced — that would require
rewriting git history, which is a separate, explicit decision.
