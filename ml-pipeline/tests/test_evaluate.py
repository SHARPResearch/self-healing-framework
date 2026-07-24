import pytest

from src.evaluate import evaluate, load_labels, percentile_threshold, pr_auc


def test_evaluate_computes_expected_metrics_on_synthetic_data():
    scores = [0.1, 0.9, 0.2, 0.8, 0.3]
    labels = [0, 1, 0, 0, 1]

    result = evaluate(scores, labels, threshold=0.7)

    assert result["n_predicted_anomalies"] == 2
    assert result["n_actual_anomalies"] == 2
    assert result["n_samples"] == 5
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5


def test_evaluate_perfect_predictions():
    scores = [0.9, 0.1, 0.95, 0.05]
    labels = [1, 0, 1, 0]

    result = evaluate(scores, labels, threshold=0.5)

    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0


def test_evaluate_raises_on_length_mismatch():
    with pytest.raises(ValueError):
        evaluate(scores=[0.1, 0.2], labels=[0], threshold=0.5)


def test_load_labels_reads_real_machine_1_1_data():
    labels = load_labels("machine-1-1")

    assert len(labels) == 28479
    assert set(labels) <= {0, 1}
    anomaly_rate = sum(labels) / len(labels)
    assert 0.05 < anomaly_rate < 0.15  # sanity check, not an exact pin


def test_load_labels_raises_for_unknown_entity():
    with pytest.raises(FileNotFoundError):
        load_labels("machine-does-not-exist")


def test_pr_auc_is_high_for_perfectly_separated_scores():
    scores = [0.1, 0.2, 0.9, 0.95]
    labels = [0, 0, 1, 1]

    assert pr_auc(scores, labels) == 1.0


def test_pr_auc_is_low_for_inverted_scores():
    scores = [0.9, 0.8, 0.1, 0.05]
    labels = [0, 0, 1, 1]

    assert pr_auc(scores, labels) < 0.6


def test_percentile_threshold_on_known_range():
    scores = list(range(1, 101))

    assert percentile_threshold(scores, 50) == pytest.approx(50.5, abs=0.5)
    assert percentile_threshold(scores, 100) == 100
    assert percentile_threshold(scores, 0) == 1
