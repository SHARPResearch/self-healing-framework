"""
nab_scorer.py — Component 1: NAB-style scoring per docs/prompts/Doc4_Claude_Code_Agent_Prompts.md P-16.

This is a simplified reimplementation of the standard NAB scoring formula, not a
byte-for-byte port of the official numenta/NAB scorer (which uses per-point sigmoid
weighting based on relative position within a window and a null-detector baseline
normalisation -- a substantially larger undertaking with its own dependencies).
Documented explicitly as such: TP/FP/FN are counted per contiguous detection window
versus label window (not per raw row), then combined with Doc4's own weights
(sigma=1.0, FP_cost=0.11, FN_cost=1.0).
"""

from datetime import datetime


def detect_windows(timestamps: list[datetime], scores: list[float], threshold: float) -> list[tuple]:
    """
    Group contiguous rows where score >= threshold into detection windows.

    Returns a list of (start, end) timestamp tuples, one per contiguous run of
    flagged rows. Matches Doc4 P-16: "Detect anomaly windows: contiguous rows
    where score > threshold" (>= here so a row exactly at threshold still counts,
    consistent with evaluate()'s convention elsewhere in this project).
    """
    windows = []
    run_start = None
    for i, (ts, score) in enumerate(zip(timestamps, scores)):
        flagged = score >= threshold
        if flagged and run_start is None:
            run_start = ts
        elif not flagged and run_start is not None:
            windows.append((run_start, timestamps[i - 1]))
            run_start = None
    if run_start is not None:
        windows.append((run_start, timestamps[-1]))
    return windows


def _overlaps(a: tuple, b: tuple) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def compute_tp_fp_fn(
    detected_windows: list[tuple],
    label_windows: list[tuple],
    timestamps: list[datetime],
    scores: list[float],
    threshold: float,
) -> tuple[int, int, int]:
    """
    TP/FN at the window level; FP at the ROW level, not the detection-window level.

    TP: one per label window that has at least one overlapping detection window.
    FN: one per label window with no overlapping detection window.
    FP: one per flagged ROW that falls outside every label window.

    Row-level FP counting is required, not a stylistic choice: window-level FP
    counting lets a detector that flags almost the entire file as one giant
    contiguous "detection window" escape penalty for free, as long as that one
    window happens to overlap every label window somewhere along its span. Caught
    this empirically on a NAB file where the model flagged 98.9% of all rows and
    window-level counting would have scored it a "perfect" 1.0.
    """
    tp = sum(
        1 for label in label_windows
        if any(_overlaps(label, det) for det in detected_windows)
    )
    fn = len(label_windows) - tp
    fp = sum(
        1 for ts, score in zip(timestamps, scores)
        if score >= threshold and not any(label[0] <= ts <= label[1] for label in label_windows)
    )
    return tp, fp, fn


def nab_score(
    tp: int, fp: int, fn: int, n_label_windows: int,
    sigma: float = 1.0, fp_cost: float = 0.11, fn_cost: float = 1.0,
) -> float | None:
    """
    Simplified NAB-style score for one file, normalised against a perfect detector.

    perfect_score is what a detector that caught every window with zero false
    positives would score (sigma per window). Returns None if there are no label
    windows (perfect_score would be zero, the ratio is undefined).
    """
    if n_label_windows == 0:
        return None
    raw_score = sigma * tp - fp_cost * fp - fn_cost * fn
    perfect_score = sigma * n_label_windows
    return raw_score / perfect_score
