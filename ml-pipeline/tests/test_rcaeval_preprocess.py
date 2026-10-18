import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "datasets" / "rcaeval"))
from preprocess import load_case  # noqa: E402


def _case(tmp_path, inject_at=6):
    t = np.arange(1000, 1012)
    df = pd.DataFrame({
        "time": t,
        "svc_cpu": np.linspace(0.1, 0.9, 12),
        "flat_mem": np.full(12, 5.0),                      # constant before the fault: dropped
        "svc_requests_total": np.cumsum(np.full(12, 3.0)),  # counter: becomes a rate of 3/s
        "time.1": t,
    })
    case = tmp_path / "svc_cpu" / "1"
    case.mkdir(parents=True)
    df.to_csv(case / "data.csv", index=False)
    (case / "inject_time.txt").write_text(str(t[inject_at]))
    return case


def test_load_case_drops_time_and_flat_columns_and_differences_counters(tmp_path):
    X, y, inject = load_case(_case(tmp_path))
    assert list(X.columns) == ["svc_cpu"]  # the rate of 3/s is constant too, so it is dropped
    assert len(X) == len(y) == 11          # one row lost to differencing
    assert inject == 5 and y[:5].sum() == 0 and y[5:].all()


def test_counter_rates_survive_when_they_vary(tmp_path):
    case = _case(tmp_path)
    df = pd.read_csv(case / "data.csv")
    df["svc_requests_total"] = np.cumsum([1, 2, 1, 3, 1, 2, 5, 1, 2, 1, 3, 1])
    df.to_csv(case / "data.csv", index=False)
    X, _, _ = load_case(case)
    assert "svc_requests_total" in X.columns
    assert X["svc_requests_total"].tolist()[:3] == [2.0, 1.0, 3.0]
