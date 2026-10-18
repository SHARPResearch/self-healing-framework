import copy
import random

from src.config import HSTConfig
from src.ensemble import RankEnsembleDetector, RobustDeviationScorer
from src.hst_model import build_model
from src.hst_state import HSTState, apply, capture, reset

CFG = HSTConfig(n_trees=5, height=6, window_size=20, seed=7, lazy=True, range_margin=0.25)


def _rows(n, seed=0):
    rng = random.Random(seed)
    return [{f"f{i}": rng.gauss(0.3, 0.02) for i in range(10)} for _ in range(n)]


def _ensemble(n_fit=200, n_calib=60, combine="mean"):
    det = RankEnsembleDetector(build_model(CFG), combine=combine)
    rows = _rows(n_fit + n_calib)
    for r in rows[:n_fit]:
        det.learn_one(r)
    det.prepare_calibration(rows[:n_fit], rows[n_fit:])
    return det


def test_robust_deviation_flags_a_single_metric_spike():
    scorer = RobustDeviationScorer().fit(_rows(300))
    normal = _rows(1, seed=5)[0]
    spike = {**normal, "f3": 0.9}
    assert scorer.score(spike) > 10 * scorer.score(normal)


def test_ensemble_scores_are_percentiles_and_max_keeps_a_single_scorer_spike():
    normal = _rows(50, seed=9)
    spike = {**normal[0], "f3": 0.9}
    mean_det, max_det = _ensemble(), _ensemble(combine="max")
    assert all(0.0 <= mean_det.score_one(r) <= 1.0 for r in normal)
    # Only the deviation scorer sees a one-metric spike: max keeps it at the top...
    assert max_det.score_one(spike) == 1.0
    # ...while mean averages it down with HST's unremarkable view of the same point.
    assert mean_det.score_one(spike) < max_det.score_one(spike)


def test_uncalibrated_ensemble_falls_back_to_the_hst_score():
    det = RankEnsembleDetector(build_model(CFG))
    for r in _rows(60):
        det.learn_one(r)
    x = _rows(1, seed=3)[0]
    assert det.score_one(x) == min(max(det.hst_model.score_one(x), 0.0), 1.0)


def test_snapshot_carries_the_ensemble_state_and_reset_clears_it():
    det = _ensemble()
    reference = copy.deepcopy(det)
    state = HSTState.from_bytes(capture(det).to_bytes())
    reset(det, keep_scaler=True)
    assert det.dev is None
    apply(det, state)
    probe = _rows(30, seed=11)
    assert [det.score_one(r) for r in probe] == [reference.score_one(r) for r in probe]
