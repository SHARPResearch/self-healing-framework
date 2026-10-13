"""
hst_model.py — Half-Space Trees anomaly detection model with MinMaxScaler preprocessing and ADWIN drift detection.

Component 1: HST model initialization, warm-up on baseline telemetry, scoring, and severity classification.
Component 2: Online streaming ingestion wrapper (HSTStreamProcessor) wrapping river.compose.Pipeline(MinMaxScaler, HalfSpaceTrees)
             with strict score_one before learn_one, ADWIN concept drift detection (delta=0.002), and state snapshots.
"""

import logging
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Generator, Iterable, Optional, Union

from river import compose, preprocessing
from river.anomaly import HalfSpaceTrees
from river.drift import ADWIN

from src.config import ADWIN_CFG, HST_CFG, ADWINConfig, HSTConfig
from src.lazy_hst import LazyHalfSpaceTrees

logger = logging.getLogger(__name__)


class FreezableMinMaxScaler(preprocessing.MinMaxScaler):
    """
    river's MinMaxScaler that stops learning once frozen.

    An online min-max scaler widens its range as soon as it sees a larger value, which moves every
    point to a different tree cell and lets a runaway metric pull "normal" along with it. Frozen
    after warm-up, the representation stays fixed and out-of-range values map outside [0, 1].
    """

    def __init__(self):
        super().__init__()
        self.frozen = False

    def learn_one(self, x):
        if not self.frozen:
            super().learn_one(x)


def freeze_scaler(model) -> None:
    """Freeze the model's scaler if it has a freezable one (no-op otherwise)."""
    if isinstance(model, compose.Pipeline):
        scaler = list(model.steps.values())[0]
        if isinstance(scaler, FreezableMinMaxScaler):
            scaler.frozen = True


def _make_hst(cfg: HSTConfig):
    if cfg.lazy:
        m = cfg.range_margin
        return LazyHalfSpaceTrees(
            n_trees=cfg.n_trees, height=cfg.height, window_size=cfg.window_size, seed=cfg.seed,
            default_limits=(-m, 1.0 + m),
        )
    return HalfSpaceTrees(
        n_trees=cfg.n_trees,
        height=cfg.height,
        window_size=cfg.window_size,
        seed=cfg.seed,
    )


def build_pipeline(cfg: Optional[HSTConfig] = None) -> compose.Pipeline:
    """Construct a river.compose.Pipeline combining a min-max scaler and Half-Space Trees."""
    if cfg is None:
        cfg = HST_CFG
    scaler = FreezableMinMaxScaler() if cfg.range_margin > 0 else preprocessing.MinMaxScaler()
    return compose.Pipeline(scaler, _make_hst(cfg))


def build_model(cfg: Optional[HSTConfig] = None, with_scaler: bool = True) -> Union[compose.Pipeline, HalfSpaceTrees]:
    """
    Construct model instance. By default wraps MinMaxScaler and HalfSpaceTrees in a river.compose.Pipeline
    to prevent disparate metric scales from distorting tree partitions. `cfg.lazy` and
    `cfg.range_margin` select the Component 1 v2 detector (see HSTConfig).
    """
    if with_scaler:
        return build_pipeline(cfg)
    if cfg is None:
        cfg = HST_CFG
    return _make_hst(cfg)


@dataclass
class WarmUpStats:
    """Summary of a warm-up training pass over normal/baseline telemetry."""
    n_events: int
    duration_seconds: float
    throughput_events_per_sec: float


def warm_up(model: Any, rows: Iterable[dict]) -> WarmUpStats:
    """
    Fit the model/pipeline on training rows via learn_one() only (no scoring).

    Training data is assumed to be mostly-normal behaviour, so warm-up establishes
    what "normal" looks like before the model is used for detection.
    """
    start = time.perf_counter()
    n_events = 0
    for features in rows:
        model.learn_one(features)
        n_events += 1
    duration = time.perf_counter() - start
    throughput = n_events / duration if duration > 0 else 0.0
    return WarmUpStats(
        n_events=n_events,
        duration_seconds=round(duration, 2),
        throughput_events_per_sec=round(throughput, 1),
    )


def score_dataset(model: Any, rows: Iterable[dict]) -> list[float]:
    """
    Score rows against an already warmed-up model, clamped to [0, 1].

    The model is frozen here — only score_one() is called, never learn_one().
    """
    return [float(min(max(model.score_one(features), 0.0), 1.0)) for features in rows]


def classify_severity(score: float) -> str:
    """
    Map a continuous anomaly score to the 4-level severity enum.

    Thresholds match services/decision-engine's PolicyEvaluator (see root CLAUDE.md
    "Anomaly severity thresholds" and docs/Doc1_Technical_Architecture.md §3.2).
    """
    if score < 0.5:
        return "watch"
    elif score < 0.7:
        return "warn"
    elif score < 0.85:
        return "degrade"
    else:
        return "critical"


@dataclass
class StreamEvent:
    """
    Result of processing one telemetry feature vector through the HST pipeline.
    Matches the schema expected by the Decision Engine, MLflow, and downstream dashboards.
    """
    step: int
    service_id: str
    anomaly_score: float
    severity: str
    drift_detected: bool
    latency_ms: float
    features: dict[str, float]
    timestamp: Optional[datetime] = None

    def __iter__(self):
        """Allows tuple unpacking: score, drift = event"""
        yield self.anomaly_score
        yield self.drift_detected


@dataclass
class RunningStats:
    """
    Rolling statistics maintained over the last N scores for monitoring.
    """
    window_size: int = 500
    _scores: list[float] = field(default_factory=list)

    def update(self, score: float) -> None:
        self._scores.append(score)
        if len(self._scores) > self.window_size:
            self._scores.pop(0)

    @property
    def mean(self) -> float:
        return sum(self._scores) / len(self._scores) if self._scores else 0.0

    @property
    def maximum(self) -> float:
        return max(self._scores) if self._scores else 0.0

    @property
    def above_warn(self) -> int:
        """Count of scores exceeding the warn threshold (0.5) in current window."""
        return sum(1 for s in self._scores if s >= 0.5)


class HSTStreamProcessor:
    """
    Model Wrapper combining river.preprocessing.MinMaxScaler and river.anomaly.HalfSpaceTrees
    into a single river.compose.Pipeline with ADWIN drift detection.

    Wraps the pipeline and strictly evaluates each observation with `score_one`
    BEFORE calling `learn_one` to prevent test data leakage. Anomaly scores are
    continuously fed into ADWIN (delta=0.002, bounding false positives at 0.2%) to flag concept drift.
    """

    def __init__(
        self,
        service_id: str = "default",
        hst_cfg: Optional[HSTConfig] = None,
        adwin_cfg: Optional[ADWINConfig] = None,
        model: Optional[Any] = None,
        delta: float = 0.002,
        with_scaler: bool = True,
    ):
        self.service_id = service_id
        self._hst_cfg = hst_cfg or HST_CFG
        self._adwin_cfg = adwin_cfg or ADWIN_CFG

        # Initialize MinMaxScaler + River HST Pipeline
        if model is not None:
            self._model = model
        else:
            self._model = build_model(self._hst_cfg, with_scaler=with_scaler)

        # Initialize ADWIN with delta=0.002 (bounds FPR at 0.2%)
        chosen_delta = delta if delta != 0.002 else self._adwin_cfg.delta
        self.adwin = ADWIN(delta=chosen_delta)
        self._adwin = self.adwin

        self._step: int = 0
        self._drift_count: int = 0
        self._last_score: float = 0.0
        self._stats = RunningStats(window_size=500)

        self._last_stable_snapshot: Optional[bytes] = None
        self._snapshot_step: int = 0

        logger.info(
            f"[{service_id}] HSTStreamProcessor initialized with river.compose.Pipeline(MinMaxScaler, HalfSpaceTrees). "
            f"n_trees={self._hst_cfg.n_trees}, height={self._hst_cfg.height}, "
            f"window_size={self._hst_cfg.window_size}, ADWIN_delta={chosen_delta}"
        )

    @property
    def model(self) -> Any:
        return self._model

    @property
    def pipeline(self) -> compose.Pipeline:
        if isinstance(self._model, compose.Pipeline):
            return self._model
        return compose.Pipeline(preprocessing.MinMaxScaler(), self._model)

    @property
    def hst_model(self) -> HalfSpaceTrees:
        if isinstance(self._model, compose.Pipeline):
            return self._model["HalfSpaceTrees"]
        return self._model

    @property
    def step(self) -> int:
        return self._step

    @property
    def drift_count(self) -> int:
        return self._drift_count

    @property
    def drift_detected(self) -> bool:
        return bool(self.adwin.drift_detected)

    @property
    def last_score(self) -> float:
        return self._last_score

    @property
    def rolling_mean_score(self) -> float:
        return self._stats.mean

    @property
    def rolling_max_score(self) -> float:
        return self._stats.maximum

    @property
    def warn_rate(self) -> float:
        """Fraction of recent scores at or above the 'warn' threshold (0.5)."""
        if self._stats._scores:
            return self._stats.above_warn / len(self._stats._scores)
        return 0.0

    def warm_up(self, train_stream: Iterable[dict], progress: bool = False) -> WarmUpStats:
        """
        Feed baseline training stream through learn_one() to initialize the normal baseline.
        """
        stats = warm_up(self._model, train_stream)
        self._last_stable_snapshot = self.snapshot()
        self._snapshot_step = stats.n_events
        logger.info(
            f"[{self.service_id}] Warm-up complete: {stats.n_events} events in "
            f"{stats.duration_seconds}s ({stats.throughput_events_per_sec} events/s)"
        )
        return stats

    def process_one(
        self,
        observation: dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> StreamEvent:
        """
        Process a single observation through MinMaxScaler -> HST scoring, online learning, and ADWIN drift detection.

        Execution order (strictly enforced to prevent test data leakage):
          1. score_one(observation) -> evaluate anomaly score against prior knowledge (MinMaxScaler + HST)
          2. learn_one(observation) -> update min-max bounds and tree weights incrementally
          3. adwin.update(anomaly_score) -> evaluate distribution change point
        """
        t_start = time.perf_counter()

        # Step 1: Score BEFORE learning to prevent test data leakage
        raw_score: float = self._model.score_one(observation)
        anomaly_score = float(min(max(raw_score, 0.0), 1.0))

        # Step 2: Incremental online update (MinMaxScaler + HST)
        self._model.learn_one(observation)

        latency_ms = (time.perf_counter() - t_start) * 1000.0

        # Step 3: Feed anomaly score directly into ADWIN drift detector
        self.adwin.update(anomaly_score)
        drift_detected = bool(self.adwin.drift_detected)

        if drift_detected:
            self._drift_count += 1
            logger.warning(
                f"[{self.service_id}] ⚠️ [DRIFT DETECTED] ADWIN detected concept drift at step {self._step}! "
                f"Anomaly Score={anomaly_score:.4f}, Total Drift Events={self._drift_count}"
            )

        # Step 4: Update stats and counter
        self._stats.update(anomaly_score)
        self._last_score = anomaly_score
        self._step += 1

        return StreamEvent(
            step=self._step,
            service_id=self.service_id,
            anomaly_score=anomaly_score,
            severity=classify_severity(anomaly_score),
            drift_detected=drift_detected,
            latency_ms=round(latency_ms, 3),
            features=observation,
            timestamp=timestamp or datetime.now(),
        )

    def score_and_learn(
        self,
        observation: dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> StreamEvent:
        """Alias for process_one."""
        return self.process_one(observation, timestamp=timestamp)

    def process_stream(
        self,
        stream: Iterable[Any],
        on_drift: Optional[Callable[["HSTStreamProcessor", StreamEvent], None]] = None,
        progress: bool = False,
    ) -> Generator[StreamEvent, None, None]:
        """
        Process an entire stream of feature dictionaries or River collector tuples.
        """
        for item in stream:
            if isinstance(item, tuple) and len(item) == 2:
                features, _ = item
                timestamp = None
            elif isinstance(item, dict) and "features" in item:
                features = item["features"]
                timestamp = item.get("timestamp")
            elif isinstance(item, dict):
                features = item
                timestamp = None
            else:
                raise ValueError(f"Unsupported stream item format: {type(item)}")

            event = self.process_one(features, timestamp=timestamp)

            if event.drift_detected and on_drift is not None:
                on_drift(self, event)

            yield event

    def snapshot(self) -> bytes:
        """Serialise current model/pipeline state to bytes (pickle)."""
        return pickle.dumps(self._model)

    def restore(self, model_bytes: bytes) -> None:
        """Restore model/pipeline state from a snapshot."""
        self._model = pickle.loads(model_bytes)
        logger.info(
            f"[{self.service_id}] Model restored from snapshot (step {self._snapshot_step})."
        )

    def take_stable_snapshot(self) -> None:
        """Mark current model state as stable checkpoint."""
        self._last_stable_snapshot = self.snapshot()
        self._snapshot_step = self._step
        logger.info(f"[{self.service_id}] Stable snapshot taken at step {self._step}.")

    def rollback_to_last_stable(self) -> bool:
        """Rollback in-memory model to last stable snapshot."""
        if self._last_stable_snapshot is None:
            logger.error(f"[{self.service_id}] Rollback failed: no stable snapshot exists.")
            return False
        self.restore(self._last_stable_snapshot)
        return True
