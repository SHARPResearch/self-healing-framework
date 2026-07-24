from river.anomaly import HalfSpaceTrees

from src.config import HSTConfig
from src.hst_model import build_model, classify_severity, warm_up


def test_build_model_applies_config():
    cfg = HSTConfig(n_trees=7, height=5, window_size=100, seed=1)
    model = build_model(cfg)
    assert isinstance(model, HalfSpaceTrees)
    assert model.n_trees == 7
    assert model.height == 5
    assert model.window_size == 100


def test_warm_up_counts_events_and_reports_throughput():
    cfg = HSTConfig(n_trees=3, height=4, window_size=25, seed=1)
    model = build_model(cfg)
    rows = [{"x": float(i % 5)} for i in range(50)]

    stats = warm_up(model, rows)

    assert stats.n_events == 50
    assert stats.duration_seconds >= 0
    assert stats.throughput_events_per_sec >= 0


def test_classify_severity_thresholds():
    assert classify_severity(0.0) == "watch"
    assert classify_severity(0.49) == "watch"
    assert classify_severity(0.5) == "warn"
    assert classify_severity(0.69) == "warn"
    assert classify_severity(0.7) == "degrade"
    assert classify_severity(0.84) == "degrade"
    assert classify_severity(0.85) == "critical"
    assert classify_severity(1.0) == "critical"
