"""
drift_detectors.py — Component 2: drift detection on the anomaly score stream.

Wraps river's ADWIN (default, per the proposal: delta=0.002), Page-Hinkley and KSWIN behind
one interface, and adds the one thing none of them report: the *direction* of the shift.
Direction matters for the lifecycle decision (src/drift_attribution.py): scores shifting up
means the model sees more of the stream as unusual (incident or new normal), scores shifting
down means the model is becoming less sensitive (suspected decay or poisoning).
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional

from river import drift

DETECTORS = ("adwin", "page_hinkley", "kswin")


def make_detector(name: str = "adwin", delta: float = 0.002, seed: int = 42):
    """Build a river drift detector by name. `delta` is ADWIN's confidence parameter."""
    if name == "adwin":
        return drift.ADWIN(delta=delta)
    if name == "page_hinkley":
        return drift.PageHinkley(mode="both")
    if name == "kswin":
        return drift.KSWIN(seed=seed)
    raise ValueError(f"Unknown drift detector {name!r}, expected one of {DETECTORS}")


@dataclass(frozen=True)
class DriftSignal:
    """One drift detection on the score stream."""
    step: int
    direction: str          # "up" | "down"
    mean_before: float
    mean_after: float


class ScoreDriftMonitor:
    """
    Feeds every anomaly score to a river drift detector and reports directional drift.

    Direction compares the mean of the most recent `recent` scores against the `reference`
    scores before them. Detections with a negligible mean change (below `min_shift`) are
    dropped as noise, since they would not change any lifecycle decision.
    """

    def __init__(
        self,
        detector: str = "adwin",
        delta: float = 0.002,
        recent: int = 50,
        reference: int = 500,
        min_shift: float = 1e-3,
    ):
        self.detector_name = detector
        self._delta = delta
        self._detector = make_detector(detector, delta)
        self._recent = recent
        self._history: deque[float] = deque(maxlen=recent + reference)
        self._min_shift = min_shift
        self.n_detections = 0

    def update(self, score: float, step: int) -> Optional[DriftSignal]:
        self._history.append(score)
        self._detector.update(score)
        if not self._detector.drift_detected:
            return None
        hist = list(self._history)
        if len(hist) <= self._recent:
            return None
        after = hist[-self._recent:]
        before = hist[:-self._recent]
        mean_after = sum(after) / len(after)
        mean_before = sum(before) / len(before)
        if abs(mean_after - mean_before) < self._min_shift:
            return None
        self.n_detections += 1
        return DriftSignal(
            step=step,
            direction="up" if mean_after > mean_before else "down",
            mean_before=round(mean_before, 6),
            mean_after=round(mean_after, 6),
        )

    def reset(self) -> None:
        """Start a fresh detector, e.g. after a model swap changes the score distribution."""
        self._detector = make_detector(self.detector_name, self._delta)
        self._history.clear()
