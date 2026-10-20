import pytest

from src.dynamic_eval import (
    anomaly_segments, event_recall, false_alarm_rate, recovery_steps, stream_metrics,
)


def test_anomaly_segments_finds_contiguous_runs_including_at_the_end():
    assert anomaly_segments([0, 1, 1, 0, 0, 1, 0, 1, 1]) == [(1, 3), (5, 6), (7, 9)]
    assert anomaly_segments([0, 0]) == []


def test_event_recall_counts_segments_with_any_alarm():
    labels = [0, 1, 1, 0, 1, 0]
    alarms = [False, False, True, False, False, False]
    assert event_recall(alarms, labels) == 0.5
    assert event_recall(alarms, [0] * 6) is None


def test_false_alarm_rate_only_looks_at_normal_points():
    assert false_alarm_rate([True, True, False, False], [1, 0, 0, 0]) == round(1 / 3, 4)


def test_recovery_is_measured_from_start_on_normal_points_only():
    labels = [0] * 1000
    alarms = [True] * 300 + [False] * 700
    # Window of 200 normal points must drop to <= 2 x 3% = 6% alarms: 12 alarms allowed.
    assert recovery_steps(alarms, labels, start=0, target_rate=0.03) == 300 + 200 - 12 - 1
    assert recovery_steps([True] * 1000, labels, start=0, target_rate=0.03) is None


def test_stream_metrics_reports_post_drift_section_and_curve():
    labels = [0] * 50 + [1] * 10 + [0] * 40
    alarms = [False] * 50 + [True] * 10 + [False] * 40
    m = stream_metrics(alarms, labels, drift_start=40, target_rate=0.03, n_slices=4)
    assert m["f1"] == 1.0 and m["post_drift_f1"] == 1.0
    assert m["fa_rate"] == 0.0 and m["event_recall"] == 1.0
    assert m["mcc"] == 1.0 and m["post_drift_mcc"] == 1.0
    assert stream_metrics([True] * 100, labels, None, 0.03)["mcc"] == 0.0  # always-alarm
    assert len(m["f1_curve"]) == 4
    assert "recovery_steps" in m
    assert "post_drift_f1" not in stream_metrics(alarms, labels, None, 0.03)


def test_length_mismatch_is_rejected():
    with pytest.raises(ValueError):
        stream_metrics([True], [0, 1], None, 0.03)


def test_simulated_operator_noise_differs_per_run():
    import random
    from evaluate_dynamic import operator_seed

    seeds = {operator_seed(e, s) for e in ("machine-1-1", "machine-2-2") for s in ("none", "silent")}
    assert len(seeds) == 4
    # with one seed shared by every run, a 20% error rate never fired on a run's first few answers
    flips = sum(random.Random(seed).random() < 0.2
                for seed in (operator_seed(f"machine-{i}", "silent") for i in range(200)))
    assert 20 <= flips <= 60
