import pytest

from src.evaluate import evaluate, load_labels


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
