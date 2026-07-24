from river.anomaly import HalfSpaceTrees

from src.config import HSTConfig
from src.hst_model import build_model, classify_severity


def test_build_model_applies_config():
    cfg = HSTConfig(n_trees=7, height=5, window_size=100, seed=1)
    model = build_model(cfg)
    assert isinstance(model, HalfSpaceTrees)
    assert model.n_trees == 7
    assert model.height == 5
    assert model.window_size == 100


def test_classify_severity_thresholds():
    assert classify_severity(0.0) == "watch"
    assert classify_severity(0.49) == "watch"
    assert classify_severity(0.5) == "warn"
    assert classify_severity(0.69) == "warn"
    assert classify_severity(0.7) == "degrade"
    assert classify_severity(0.84) == "degrade"
    assert classify_severity(0.85) == "critical"
    assert classify_severity(1.0) == "critical"
