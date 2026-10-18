#!/usr/bin/env python3
"""
preprocess.py — Turn one RCAEval RE1 failure case into a labelled metric stream.

Each case directory (raw/RE1-OB/<service>_<fault>/<n>/) holds data.csv (one row per second,
Prometheus/cAdvisor metrics of every service) and inject_time.txt (Unix time the fault was injected).
Online Boutique cases already hold rates and gauges; Sock Shop cases hold raw Prometheus counters
(names ending in "total"), which only ever grow and are turned into per-second rates here. Column
sets differ slightly between cases (arXiv 2609.27069 notes the inconsistent RE1 schemas), so every
case is processed on its own and the detector is fitted per case.

load_case() returns (features, labels, inject_index):
  features      DataFrame, numeric, no time columns, counters differenced, columns constant over the
                pre-fault period dropped (they carry no information for a model fitted on it)
  labels        0 before the injection, 1 from the injection onward
  inject_index  row index of the first post-injection row
"""

from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).parent / "raw"


def list_cases(system: str) -> list[Path]:
    """Case directories for 'RE1-OB' or 'RE1-SS', sorted."""
    return sorted(p.parent for p in (RAW_DIR / system).glob("*/*/data.csv"))


def load_case(case_dir: Path) -> tuple[pd.DataFrame, np.ndarray, int]:
    df = pd.read_csv(case_dir / "data.csv")
    inject = int(float((case_dir / "inject_time.txt").read_text().strip()))
    time = df["time"].to_numpy()
    df = df.drop(columns=[c for c in df.columns if c == "time" or c.startswith("time.")])
    df = df.apply(pd.to_numeric, errors="coerce").ffill().bfill().fillna(0.0)

    counters = [c for c in df.columns if c.endswith("total")]
    if counters:
        rates = df[counters].diff().clip(lower=0)  # counter resets show up as negative steps
        df[counters] = rates
        df, time = df.iloc[1:].reset_index(drop=True), time[1:]

    labels = (time >= inject).astype(int)
    inject_index = int(np.argmax(labels)) if labels.any() else len(labels)
    pre = df.iloc[:inject_index]
    df = df.loc[:, pre.std() > 1e-12]
    return df.astype(float), labels, inject_index


if __name__ == "__main__":
    for system in ("RE1-OB", "RE1-SS"):
        cases = list_cases(system)
        feats, label_rate = [], []
        for case in cases:
            X, y, _ = load_case(case)
            feats.append(X.shape[1])
            label_rate.append(y.mean())
        print(f"{system}: {len(cases)} cases, features {min(feats)}-{max(feats)}, "
              f"post-injection share {np.mean(label_rate):.2f}")
