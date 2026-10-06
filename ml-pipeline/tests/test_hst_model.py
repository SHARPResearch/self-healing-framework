from river import compose
from river.anomaly import HalfSpaceTrees
from river.preprocessing import MinMaxScaler

from src.config import HSTConfig
from src.hst_model import build_model, build_pipeline, classify_severity, score_dataset, warm_up


def test_build_model_applies_config():
    cfg = HSTConfig(n_trees=7, height=5, window_size=100, seed=1)
    pipeline = build_model(cfg)
    assert isinstance(pipeline, compose.Pipeline)
    assert isinstance(pipeline["MinMaxScaler"], MinMaxScaler)
    assert isinstance(pipeline["HalfSpaceTrees"], HalfSpaceTrees)
    assert pipeline["HalfSpaceTrees"].n_trees == 7
    assert pipeline["HalfSpaceTrees"].height == 5
    assert pipeline["HalfSpaceTrees"].window_size == 100

    raw_model = build_model(cfg, with_scaler=False)
    assert isinstance(raw_model, HalfSpaceTrees)
    assert raw_model.n_trees == 7


def test_warm_up_counts_events_and_reports_throughput():
    cfg = HSTConfig(n_trees=3, height=4, window_size=25, seed=1)
    model = build_model(cfg)
    rows = [{"x": float(i % 5)} for i in range(50)]

    stats = warm_up(model, rows)

    assert stats.n_events == 50
    assert stats.duration_seconds >= 0
    assert stats.throughput_events_per_sec >= 0


def test_score_dataset_returns_one_clamped_score_per_row():
    cfg = HSTConfig(n_trees=3, height=4, window_size=25, seed=1)
    model = build_model(cfg)
    warm_up(model, [{"x": float(i % 5)} for i in range(50)])

    scores = score_dataset(model, [{"x": 1.0}, {"x": 99.0}, {"x": 2.0}])

    assert len(scores) == 3
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_classify_severity_thresholds():
    assert classify_severity(0.0) == "watch"
    assert classify_severity(0.49) == "watch"
    assert classify_severity(0.5) == "warn"
    assert classify_severity(0.69) == "warn"
    assert classify_severity(0.7) == "degrade"
    assert classify_severity(0.84) == "degrade"
    assert classify_severity(0.85) == "critical"
    assert classify_severity(1.0) == "critical"


def test_minmax_scaler_hst_disparate_scales():
    """Test that MinMaxScaler + HST detects anomalies with massive scale differences"""
    cfg = HSTConfig(n_trees=10, height=8, window_size=50, seed=42)
    pipe = build_model(cfg)
    # Warm up with baseline
    baseline_rows = [
        {"cpu_rate": 0.2 + (i % 5) * 0.01, "memory_usage": 7.0e8 + (i % 10) * 1e6, "network_receive_rate": 4.0e4 + (i % 3) * 1e3}
        for i in range(100)
    ]
    warm_up(pipe, baseline_rows)
    
    # Anomaly with scaled down memory and CPU
    anomaly_obs = {"cpu_rate": 0.05, "memory_usage": 4.5e8, "network_receive_rate": 1.5e4}
    score = pipe.score_one(anomaly_obs)
    assert score > 0.5
