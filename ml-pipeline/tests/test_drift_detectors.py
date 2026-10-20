import random

import pytest

from src.drift_detectors import DETECTORS, ScoreDriftMonitor, make_detector


def _stream(levels, n_each=600, seed=0):
    rng = random.Random(seed)
    return [lvl + rng.gauss(0, 0.02) for lvl in levels for _ in range(n_each)]


def _signals(monitor, scores):
    return [s for i, x in enumerate(scores) if (s := monitor.update(x, i)) is not None]


@pytest.mark.parametrize("name", DETECTORS)
def test_every_detector_can_be_built(name):
    assert make_detector(name) is not None


def test_unknown_detector_name_is_rejected():
    with pytest.raises(ValueError):
        make_detector("nope")


def test_upward_shift_is_reported_as_up():
    signals = _signals(ScoreDriftMonitor(), _stream([0.1, 0.5]))
    assert signals, "ADWIN should flag a 0.1 -> 0.5 mean shift"
    assert signals[0].direction == "up"
    assert signals[0].step >= 600
    assert signals[0].mean_after > signals[0].mean_before


def test_downward_shift_is_reported_as_down():
    signals = _signals(ScoreDriftMonitor(), _stream([0.5, 0.1]))
    assert signals and signals[0].direction == "down"


def test_stationary_stream_rarely_fires():
    monitor = ScoreDriftMonitor()
    assert len(_signals(monitor, _stream([0.2], n_each=3000))) <= 1


def test_reset_clears_history():
    monitor = ScoreDriftMonitor()
    _signals(monitor, _stream([0.1, 0.5]))
    monitor.reset()
    assert monitor.update(0.3, 0) is None
