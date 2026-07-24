from src.hst_model import classify_severity


def test_classify_severity_thresholds():
    assert classify_severity(0.0) == "watch"
    assert classify_severity(0.49) == "watch"
    assert classify_severity(0.5) == "warn"
    assert classify_severity(0.69) == "warn"
    assert classify_severity(0.7) == "degrade"
    assert classify_severity(0.84) == "degrade"
    assert classify_severity(0.85) == "critical"
    assert classify_severity(1.0) == "critical"
