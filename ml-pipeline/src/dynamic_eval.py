"""
dynamic_eval.py — Component 2: evaluation of a lifecycle policy's alarm stream against SMD labels.

Labels are only used here, after the fact. Nothing in the lifecycle manager ever sees them, so
every policy is evaluated exactly as it would run unsupervised in production. Each policy is
judged on the alarms it actually raised with whatever model and threshold it was serving at the
time (a promoted challenger brings its own threshold), not on a re-thresholded score array.

Metrics:
  precision / recall / f1          point-wise, whole test stream
  mcc                              Matthews correlation, point-wise. Reported next to F1 because
                                   F1 rewards a stale model that flags everything when anomalies
                                   are frequent (F1 of always-alarm = 2p/(1+p)); MCC is 0 for any
                                   constant predictor.
  post_drift_*                     the same, from the first injected drift onward
  event_recall                     fraction of labelled anomaly segments with at least one alarm
  fa_rate / post_drift_fa_rate     alarm rate on normal points (false alarms per normal event)
  recovery_steps                   events after the first drift until the rolling false-alarm
                                   rate on normal points is back under 2 x target (None = never)
  f1_curve                         point-wise F1 per tenth of the stream (accuracy over time)
"""

from typing import Optional

from sklearn.metrics import f1_score, matthews_corrcoef, precision_score, recall_score


def _prf(alarms: list[bool], labels: list[int]) -> tuple[float, float, float]:
    pred = [int(a) for a in alarms]
    return (
        round(precision_score(labels, pred, zero_division=0), 4),
        round(recall_score(labels, pred, zero_division=0), 4),
        round(f1_score(labels, pred, zero_division=0), 4),
    )


def anomaly_segments(labels: list[int]) -> list[tuple[int, int]]:
    """[start, end) index ranges of contiguous labelled anomalies."""
    segs, start = [], None
    for i, y in enumerate(labels):
        if y and start is None:
            start = i
        elif not y and start is not None:
            segs.append((start, i))
            start = None
    if start is not None:
        segs.append((start, len(labels)))
    return segs


def event_recall(alarms: list[bool], labels: list[int]) -> Optional[float]:
    segs = anomaly_segments(labels)
    if not segs:
        return None
    hit = sum(1 for s, e in segs if any(alarms[s:e]))
    return round(hit / len(segs), 4)


def false_alarm_rate(alarms: list[bool], labels: list[int]) -> Optional[float]:
    normal = [a for a, y in zip(alarms, labels) if not y]
    return round(sum(normal) / len(normal), 4) if normal else None


def recovery_steps(
    alarms: list[bool], labels: list[int], start: int, target_rate: float, window: int = 200,
) -> Optional[int]:
    """Events from `start` until the rolling normal-only alarm rate first drops to <= 2 x target."""
    limit = 2 * target_rate
    recent: list[bool] = []
    for i in range(start, len(alarms)):
        if labels[i]:
            continue
        recent.append(alarms[i])
        if len(recent) > window:
            recent.pop(0)
        if len(recent) == window and sum(recent) / window <= limit:
            return i - start
    return None


def stream_metrics(
    alarms: list[bool], labels: list[int], drift_start: Optional[int], target_rate: float,
    n_slices: int = 10,
) -> dict:
    if len(alarms) != len(labels):
        raise ValueError(f"alarm/label length mismatch: {len(alarms)} vs {len(labels)}")
    p, r, f = _prf(alarms, labels)
    out = {
        "precision": p, "recall": r, "f1": f,
        "mcc": round(float(matthews_corrcoef(labels, [int(a) for a in alarms])), 4),
        "event_recall": event_recall(alarms, labels),
        "fa_rate": false_alarm_rate(alarms, labels),
    }
    if drift_start is not None:
        pa, ra, fa = _prf(alarms[drift_start:], labels[drift_start:])
        out.update({
            "post_drift_precision": pa, "post_drift_recall": ra, "post_drift_f1": fa,
            "post_drift_mcc": round(float(matthews_corrcoef(
                labels[drift_start:], [int(a) for a in alarms[drift_start:]])), 4),
            "post_drift_fa_rate": false_alarm_rate(alarms[drift_start:], labels[drift_start:]),
            "recovery_steps": recovery_steps(alarms, labels, drift_start, target_rate),
        })
    n = len(alarms)
    bounds = [round(i * n / n_slices) for i in range(n_slices + 1)]
    out["f1_curve"] = [_prf(alarms[a:b], labels[a:b])[2] for a, b in zip(bounds, bounds[1:])]
    return out
