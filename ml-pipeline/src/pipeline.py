"""
pipeline.py — Component 1: the one training and evaluation code path.

train.py (single entity CLI), sweep_hyperparams.py, and train_all.py all call
train_and_evaluate() so there is exactly one place that does preprocessing, warm up,
scoring, evaluation, model saving, and MLflow logging.
"""

import csv
import logging
import pickle
import sys
from pathlib import Path
from typing import TypedDict

import mlflow
import pandas as pd
from river.anomaly import HalfSpaceTrees

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "datasets" / "smd"))
from preprocess import preprocess_entity  # noqa: E402

from src.config import PIPELINE_CFG, HSTConfig  # noqa: E402
from src.evaluate import evaluate, load_labels  # noqa: E402
from src.hst_model import (  # noqa: E402
    WarmUpStats, build_model, classify_severity, score_dataset, warm_up,
)

logger = logging.getLogger(__name__)


class WarmUpAndScoreResult(TypedDict):
    model: HalfSpaceTrees
    scores: list[float]
    labels: list[int]
    warm_up_stats: WarmUpStats


def warm_up_and_score(entity_id: str, hst_cfg: HSTConfig) -> WarmUpAndScoreResult:
    """
    Preprocess, warm up, and score one SMD entity. No persistence, no MLflow.

    This is the fast path used by sweeps that need scores at many thresholds or many
    hyperparameter combinations without paying for model/CSV I/O or MLflow runs each time.
    """
    train_path = preprocess_entity(entity_id, split="train")
    test_path = preprocess_entity(entity_id, split="test")
    train_df = pd.read_parquet(train_path)
    test_df = pd.read_parquet(test_path)

    model = build_model(hst_cfg)
    warm_up_stats = warm_up(model, train_df.to_dict(orient="records"))
    scores = score_dataset(model, test_df.to_dict(orient="records"))
    labels = load_labels(entity_id)
    return WarmUpAndScoreResult(
        model=model, scores=scores, labels=labels, warm_up_stats=warm_up_stats
    )


class TrainResult(TypedDict):
    entity_id: str
    warm_up_events: int
    warm_up_throughput_eps: float
    precision: float
    recall: float
    f1: float
    n_actual_anomalies: int
    n_samples: int


def train_and_evaluate(
    entity_id: str,
    hst_cfg: HSTConfig,
    eval_threshold: float,
    save_model: bool = True,
    save_scores_csv: bool = True,
    log_to_mlflow: bool = True,
) -> TrainResult:
    """
    Run the full Component 1 flow for one SMD entity: preprocess, warm up, score the
    test split (model frozen), evaluate against ground truth, optionally persist the
    model/scores/MLflow run.

    Args:
        entity_id: SMD entity id, e.g. "machine-1-1".
        hst_cfg: HalfSpaceTrees hyperparameters to use for this run.
        eval_threshold: score threshold for anomaly prediction.
        save_model: pickle the trained model to model_snapshots/.
        save_scores_csv: write per row scores to outputs/scores/.
        log_to_mlflow: log params/metrics (and the model artifact, if saved) to MLflow.

    Returns:
        TrainResult with warm up stats and evaluation metrics.
    """
    if log_to_mlflow:
        mlflow.set_tracking_uri(PIPELINE_CFG.mlflow_tracking_uri)
        mlflow.set_experiment(f"hst_{entity_id}")
        mlflow.start_run(run_name=f"{entity_id}_component1")

    try:
        if log_to_mlflow:
            mlflow.log_params({
                "n_trees": hst_cfg.n_trees,
                "height": hst_cfg.height,
                "window_size": hst_cfg.window_size,
                "seed": hst_cfg.seed,
                "entity_id": entity_id,
                "eval_threshold": eval_threshold,
            })

        result = warm_up_and_score(entity_id, hst_cfg)
        model, scores, labels, warm_up_stats = (
            result["model"], result["scores"], result["labels"], result["warm_up_stats"]
        )
        severities = [classify_severity(s) for s in scores]
        metrics = evaluate(scores, labels, threshold=eval_threshold)

        if log_to_mlflow:
            mlflow.log_metrics({
                "eval_precision": metrics["precision"],
                "eval_recall": metrics["recall"],
                "eval_f1": metrics["f1"],
                "warm_up_events": warm_up_stats.n_events,
                "warm_up_throughput_eps": warm_up_stats.throughput_events_per_sec,
                "mean_test_score": sum(scores) / len(scores),
            })

        if save_model:
            snapshot_dir = Path(PIPELINE_CFG.model_snapshot_dir) / entity_id
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            model_path = snapshot_dir / f"hst_model_step_{warm_up_stats.n_events}.pkl"
            model_path.write_bytes(pickle.dumps(model))
            if log_to_mlflow:
                mlflow.log_artifact(str(model_path), artifact_path="model")

        if save_scores_csv:
            score_dir = Path(PIPELINE_CFG.score_output_dir)
            score_dir.mkdir(parents=True, exist_ok=True)
            scores_path = score_dir / f"{entity_id}_scores.csv"
            with open(scores_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["step", "anomaly_score", "severity", "label"])
                for step, (score, severity, label) in enumerate(
                    zip(scores, severities, labels), start=1
                ):
                    writer.writerow([step, round(score, 6), severity, label])
    except Exception:
        if log_to_mlflow:
            mlflow.end_run(status="FAILED")
        raise
    else:
        if log_to_mlflow:
            mlflow.end_run(status="FINISHED")

    return TrainResult(
        entity_id=entity_id,
        warm_up_events=warm_up_stats.n_events,
        warm_up_throughput_eps=warm_up_stats.throughput_events_per_sec,
        precision=metrics["precision"],
        recall=metrics["recall"],
        f1=metrics["f1"],
        n_actual_anomalies=metrics["n_actual_anomalies"],
        n_samples=metrics["n_samples"],
    )
