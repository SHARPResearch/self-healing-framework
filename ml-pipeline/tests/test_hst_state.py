import copy
import random

import pytest

from src.config import HSTConfig
from src.hst_model import build_model
from src.hst_state import (
    HSTState, apply, capture, feature_names, materialize, reset, structure_fingerprint,
)

CFG = HSTConfig(n_trees=5, height=6, window_size=20, seed=7)


def _rows(n, seed=0, shift=0.0):
    rng = random.Random(seed)
    return [{"a": rng.random() * 0.5 + shift, "b": rng.random() * 0.3} for _ in range(n)]


def _scores(model, rows):
    return [model.score_one(r) for r in rows]


@pytest.mark.parametrize("with_scaler", [True, False])
def test_apply_restores_exact_scores_after_further_learning(with_scaler):
    model = build_model(CFG, with_scaler=with_scaler)
    for r in _rows(70):
        model.learn_one(r)
    reference = copy.deepcopy(model)
    state = capture(model)

    for r in _rows(90, seed=1, shift=0.4):
        model.learn_one(r)
    probe = _rows(30, seed=2)
    assert _scores(model, probe) != _scores(reference, probe)

    apply(model, state)
    assert _scores(model, probe) == _scores(reference, probe)
    # Learning continues identically from the restored point too.
    more = _rows(25, seed=3)
    for r in more:
        model.learn_one(r)
        reference.learn_one(r)
    assert _scores(model, probe) == _scores(reference, probe)


def test_bytes_round_trip_is_lossless():
    model = build_model(CFG)
    for r in _rows(55):
        model.learn_one(r)
    state = capture(model, meta={"reason": "test"})
    restored = HSTState.from_bytes(state.to_bytes())
    assert restored.masses == state.masses
    assert restored.counter == state.counter
    assert restored.first_window == state.first_window
    assert restored.meta == {"reason": "test"}


def test_reset_matches_a_freshly_built_model_with_same_seed():
    model = build_model(CFG)
    for r in _rows(60):
        model.learn_one(r)
    reset(model)
    fresh = build_model(CFG)
    rows = _rows(50, seed=5)
    for r in rows:
        model.learn_one(r)
        fresh.learn_one(r)
    probe = _rows(20, seed=6)
    assert _scores(model, probe) == _scores(fresh, probe)


def test_snapshot_only_stores_nodes_with_mass():
    model = build_model(CFG, with_scaler=False)
    for r in _rows(40):
        model.learn_one(r)
    state = capture(model)
    total_nodes = CFG.n_trees * (2 ** (CFG.height + 1) - 1)
    assert 0 < state.n_massive_nodes < total_nodes


def test_apply_rejects_a_model_with_different_structure():
    a = build_model(CFG)
    b = build_model(HSTConfig(n_trees=5, height=6, window_size=20, seed=8))
    for r in _rows(30):
        a.learn_one(r)
        b.learn_one(r)
    assert structure_fingerprint(a) != structure_fingerprint(b)
    with pytest.raises(ValueError):
        apply(b, capture(a))


def test_materialize_builds_identical_structure_without_data():
    trained = build_model(CFG)
    for r in _rows(60):
        trained.learn_one(r)
    replica = build_model(CFG)
    materialize(replica, feature_names(trained))
    assert feature_names(trained) == ["a", "b"]
    assert structure_fingerprint(replica) == structure_fingerprint(trained)
    apply(replica, capture(trained))
    probe = _rows(20, seed=9)
    assert _scores(replica, probe) == _scores(trained, probe)


def test_capture_requires_a_built_model():
    with pytest.raises(ValueError):
        capture(build_model(CFG))
