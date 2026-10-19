from datetime import datetime as dt
from datetime import timedelta

import pytest

from src.nab_scorer import compute_tp_fp_fn, detect_windows, nab_score


def test_detect_windows_groups_contiguous_flagged_rows():
    ts = [dt(2020, 1, 1, 0, i) for i in range(10)]
    scores = [0.1, 0.1, 0.9, 0.9, 0.1, 0.1, 0.9, 0.1, 0.1, 0.1]

    windows = detect_windows(ts, scores, threshold=0.5)

    assert windows == [
        (dt(2020, 1, 1, 0, 2), dt(2020, 1, 1, 0, 3)),
        (dt(2020, 1, 1, 0, 6), dt(2020, 1, 1, 0, 6)),
    ]


def test_detect_windows_handles_no_flags():
    ts = [dt(2020, 1, 1, 0, i) for i in range(5)]
    scores = [0.1] * 5

    assert detect_windows(ts, scores, threshold=0.5) == []


def test_compute_tp_fp_fn_counts_fp_at_row_level():
    ts = [dt(2020, 1, 1, 0, i) for i in range(10)]
    scores = [0.1, 0.1, 0.9, 0.9, 0.1, 0.1, 0.9, 0.1, 0.1, 0.1]
    detected = detect_windows(ts, scores, threshold=0.5)
    labels = [(dt(2020, 1, 1, 0, 2), dt(2020, 1, 1, 0, 4))]

    tp, fp, fn = compute_tp_fp_fn(detected, labels, ts, scores, threshold=0.5)

    # the window at minute 6 is a single flagged row outside the label window
    assert (tp, fp, fn) == (1, 1, 0)


def test_compute_tp_fp_fn_counts_missed_window_as_fn():
    ts = [dt(2020, 1, 1, 0, i) for i in range(10)]
    scores = [0.1] * 10
    detected = detect_windows(ts, scores, threshold=0.5)
    labels = [(dt(2020, 1, 1, 0, 2), dt(2020, 1, 1, 0, 4))]

    tp, fp, fn = compute_tp_fp_fn(detected, labels, ts, scores, threshold=0.5)

    assert (tp, fp, fn) == (0, 0, 1)


def test_compute_tp_fp_fn_penalises_one_giant_over_flagging_window():
    """
    Regression test for the bug found on a real NAB file: a detector that
    flags almost the whole series as one contiguous window must not score a
    "perfect" result just because that window happens to overlap every label.
    """
    base = dt(2020, 1, 1)
    ts = [base + timedelta(minutes=i) for i in range(100)]
    scores = [0.9] * 100  # flags everything
    detected = detect_windows(ts, scores, threshold=0.5)
    labels = [(base + timedelta(minutes=10), base + timedelta(minutes=12))]

    tp, fp, fn = compute_tp_fp_fn(detected, labels, ts, scores, threshold=0.5)

    assert tp == 1
    assert fn == 0
    assert fp == 97  # every flagged row except the 3 inside the label window


def test_nab_score_perfect_detector_scores_one():
    assert nab_score(tp=3, fp=0, fn=0, n_label_windows=3) == pytest.approx(1.0)


def test_nab_score_null_detector_scores_negative_fn_cost():
    assert nab_score(tp=0, fp=0, fn=3, n_label_windows=3) == pytest.approx(-1.0)


def test_nab_score_returns_none_for_no_label_windows():
    assert nab_score(tp=0, fp=1, fn=0, n_label_windows=0) is None
