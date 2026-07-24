#!/usr/bin/env python3
"""
preprocess.py — Standardise raw SMD entity files into the canonical feature schema.

Per docs/Doc3_Execution_Guide.md Phase 2: loads datasets/smd/raw/{split}/{entity_id}.txt
(comma-separated, no header, 38 columns) and writes datasets/smd/processed/{entity_id}.parquet
with the first 6 columns renamed to the canonical Prometheus-compatible schema. Columns beyond
the canonical 6 are kept as feat_06..feat_37 since HST is non-parametric and benefits from all
available features (see docs/Component_1_2_Technical_Guide.md Part 3 for the full rationale).

Usage:
    python preprocess.py --entity machine-1-1 --split train
    python preprocess.py --all   # process every entity/split found under raw/
"""

import argparse
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "raw"
PROCESSED_DIR = Path(__file__).parent / "processed"

N_COLUMNS = 38
CANONICAL_MAP = {
    "feat_00": "cpu_rate",
    "feat_01": "memory_used",
    "feat_02": "network_rx",
    "feat_03": "network_tx",
    "feat_04": "disk_io_read",
    "feat_05": "disk_io_write",
}
COLUMN_NAMES = [f"feat_{i:02d}" for i in range(N_COLUMNS)]


def preprocess_entity(entity_id: str, split: str) -> Path:
    raw_path = RAW_DIR / split / f"{entity_id}.txt"
    if not raw_path.exists():
        raise FileNotFoundError(f"{raw_path} not found — run ./download.sh first")

    df = pd.read_csv(raw_path, header=None, names=COLUMN_NAMES)
    df = df.rename(columns=CANONICAL_MAP)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / f"{entity_id}_{split}.parquet"
    df.to_parquet(out_path, index=False)
    return out_path


def discover_entities(split: str) -> list[str]:
    split_dir = RAW_DIR / split
    return sorted(p.stem for p in split_dir.glob("*.txt")) if split_dir.exists() else []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", help="Entity ID, e.g. machine-1-1")
    parser.add_argument("--split", default="train", choices=["train", "test"])
    parser.add_argument("--all", action="store_true", help="Process every entity/split under raw/")
    args = parser.parse_args()

    if args.all:
        for split in ("train", "test"):
            for entity_id in discover_entities(split):
                out = preprocess_entity(entity_id, split)
                print(f"wrote {out}")
        return

    if not args.entity:
        parser.error("--entity is required unless --all is given")

    out = preprocess_entity(args.entity, args.split)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
