import copy
import random

from src.detectors import PCADetector, SmoothedDetector
from src.hst_model import build_model, detector_config
from src.hst_state import HSTState, apply, capture, feature_names, materialize, reset


def _correlated_rows(n, seed=0):
    """Three metrics driven by one load signal (like CPU, network and disk), plus noise."""
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        load = rng.uniform(0.2, 0.8)
        rows.append({"cpu": load + rng.gauss(0, 0.01), "net": 0.9 * load + rng.gauss(0, 0.01),
                     "disk": 0.5 * load + rng.gauss(0, 0.01), "flat": 0.3})
    return rows


def _fitted(det, n_fit=400, n_calib=100):
    rows = _correlated_rows(n_fit + n_calib)
    for r in rows[:n_fit]:
        det.learn_one(r)
    det.prepare_calibration(rows[:n_fit], rows[n_fit:])
    return det


def test_pca_flags_a_correlation_break_with_every_metric_in_range():
    det = _fitted(PCADetector())
    normal = _correlated_rows(200, seed=5)
    # cpu high but network and disk low: each value is inside its normal range, the mix is not.
    broken = {"cpu": 0.75, "net": 0.2, "disk": 0.1, "flat": 0.3}
    assert det.spe(broken) > 10 * max(det.spe(r) for r in normal)
    assert det.score_one(broken) > max(det.score_one(r) for r in normal)
    assert all(0.0 <= det.score_one(r) < 1.0 for r in normal + [broken])


def test_pca_scores_zero_before_it_is_fitted():
    assert PCADetector().score_one({"a": 1.0}) == 0.0


def test_smoothing_averages_over_recent_events_and_damps_one_off_spikes():
    det = _fitted(SmoothedDetector(PCADetector(), span=5))
    normal = _correlated_rows(50, seed=7)
    for r in normal:
        det.score_one(r)
    spike_raw = det.base.score_one({"cpu": 0.75, "net": 0.2, "disk": 0.1, "flat": 0.3})
    smoothed = det.score_one({"cpu": 0.75, "net": 0.2, "disk": 0.1, "flat": 0.3})
    assert 0 < smoothed < spike_raw  # a single spike is pulled towards the recent level
    for _ in range(20):
        smoothed = det.score_one({"cpu": 0.75, "net": 0.2, "disk": 0.1, "flat": 0.3})
    assert smoothed > 0.95 * spike_raw  # a sustained anomaly reaches its full score


def test_pca_snapshot_round_trip_and_replica_restore():
    det = _fitted(SmoothedDetector(PCADetector(), span=5))
    for r in _correlated_rows(10, seed=8):
        det.score_one(r)
    reference = copy.deepcopy(det)
    state = HSTState.from_bytes(capture(det).to_bytes())
    assert state.masses == []  # no trees to capture

    replica = build_model(detector_config("pca_s5"))
    materialize(replica, feature_names(det))
    apply(replica, state)
    probe = _correlated_rows(30, seed=9)
    assert [replica.score_one(r) for r in probe] == [reference.score_one(r) for r in probe]


def test_reset_clears_the_fit_but_keeps_the_features():
    det = _fitted(PCADetector())
    reset(det)
    assert det.axes is None and det.features == ["cpu", "net", "disk", "flat"]
    assert det.score_one(_correlated_rows(1)[0]) == 0.0


def test_presets_build_the_selected_detectors():
    assert isinstance(build_model(detector_config("pca")), PCADetector)
    smoothed = build_model(detector_config("pca_s5"))
    assert isinstance(smoothed, SmoothedDetector) and smoothed.span == 5
    assert isinstance(smoothed.base, PCADetector)
