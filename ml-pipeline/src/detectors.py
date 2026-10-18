"""
detectors.py — Component 1 v3: PCA reconstruction-error detector and score smoothing.

Why PCA. On the SMD development entities a PCA reconstruction-error detector (squared prediction
error, SPE) ranked anomalies far better than Half-Space Trees: mean PR-AUC 0.355 vs 0.220, and
0.397 once its score was lightly smoothed (compare_detectors.py, RESULTS.md "Detector v3"). This
matches Audibert et al. (Pattern Recognition 2022, "Do deep neural networks contribute to
multivariate time series anomaly detection?"): conventional methods are competitive on SMD. SMD
metrics are strongly correlated (CPU, load, network and disk move together), so a point that breaks
those correlations leaves a large residual off the principal subspace even when every single metric
is inside its usual range, which is where a single-point random partition like HST is weakest.

PCADetector is fitted in one batch on warm-up data and then serves frozen, which is how CADAL
serves every model anyway: a model only changes at a versioned, validated transition (a challenger
is fitted on the quarantine buffer, see src/lifecycle_manager.py). Its whole learned state is the
robust centring, the principal axes and the residual reference, a few KB carried in HSTState.extra.

SmoothedDetector wraps any detector and returns an exponentially weighted moving average of its
score. SMD anomalies are segments, not single points, so a short EWMA (span 5 events) suppresses
isolated false alarms at the cost of a few events of detection delay.

Contract (same as src/ensemble.RankEnsembleDetector, so the lifecycle, calibration and snapshots
need nothing new): learn_one, score_one, prepare_calibration(fit_rows, calib_rows), extra_state,
set_extra_state, clear_extra, plus `hst_model = None` and `fingerprint()` to tell
src/hst_state.py there is no tree state to capture.
"""

import hashlib
import json

import numpy as np

CLIP = 10.0          # robust z-scores are clipped so one exploding metric cannot dominate the fit
VARIANCE_KEPT = 0.95


class PCADetector:
    """Squared prediction error off the principal subspace of robust-standardised features."""

    hst_model = None

    def __init__(self, variance: float = VARIANCE_KEPT):
        self.variance = variance
        self.features: list[str] | None = None
        self.median = self.scale = self.mean = self.axes = None

    # ── fitting ──────────────────────────────────────────────────────────────
    def learn_one(self, x):
        """Frozen-serving detector: fitting happens in prepare_calibration, on a batch."""
        if self.features is None:
            self.features = list(x)

    def prepare_calibration(self, fit_rows: list[dict], calib_rows: list[dict]) -> None:
        self.features = list(fit_rows[0])
        X = self._matrix(fit_rows)
        self.median = np.median(X, axis=0)
        mad = 1.4826 * np.median(np.abs(X - self.median), axis=0)
        self.scale = np.maximum(np.where(mad > 1e-9, mad, X.std(axis=0)), 1e-6)
        Z = self._standardise(X)
        self.mean = Z.mean(axis=0)
        _, s, vt = np.linalg.svd(Z - self.mean, full_matrices=False)
        explained = s ** 2 / max(float((s ** 2).sum()), 1e-12)
        k = int(np.searchsorted(np.cumsum(explained), self.variance) + 1)
        self.axes = vt[:k]

    # ── scoring ──────────────────────────────────────────────────────────────
    def _matrix(self, rows: list[dict]) -> np.ndarray:
        return np.array([[r[f] for f in self.features] for r in rows], dtype=float)

    def _standardise(self, X: np.ndarray) -> np.ndarray:
        return np.clip((X - self.median) / self.scale, -CLIP, CLIP)

    def spe(self, x) -> float:
        """Squared prediction error: squared distance from the principal subspace."""
        if self.axes is None:
            return 0.0
        z = self._standardise(np.fromiter((x[f] for f in self.features), dtype=float,
                                          count=len(self.features)))
        d = z - self.mean
        residual = d - (self.axes @ d) @ self.axes
        return float(residual @ residual)

    def raw_score(self, x) -> float:
        return self.spe(x)

    @staticmethod
    def squash(e: float) -> float:
        """
        Map an SPE into [0, 1) by e / (1 + e): strictly increasing, so ranking and percentile
        calibration are unchanged, but bounded like every other detector score (the lifecycle
        clamps scores to [0, 1], which would otherwise flatten every large error to 1.0).
        """
        return e / (1.0 + e)

    @staticmethod
    def unsquash(s: float) -> float:
        """Inverse of squash, so tail fits (POT thresholds) see the real error scale."""
        s = min(s, 1.0 - 1e-12)
        return s / (1.0 - s)

    def score_one(self, x) -> float:
        return self.squash(self.spe(x))

    # ── snapshot contract ────────────────────────────────────────────────────
    def fingerprint(self) -> str:
        payload = json.dumps({"kind": "pca", "variance": self.variance, "features": self.features})
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def extra_state(self) -> dict | None:
        if self.axes is None:
            return None
        return {"features": self.features, "median": self.median.tolist(),
                "scale": self.scale.tolist(), "mean": self.mean.tolist(),
                "axes": self.axes.tolist()}

    def set_extra_state(self, state: dict | None) -> None:
        if state is None:
            self.clear_extra()
            return
        self.features = state["features"]
        self.median, self.scale = np.asarray(state["median"]), np.asarray(state["scale"])
        self.mean, self.axes = np.asarray(state["mean"]), np.asarray(state["axes"])

    def clear_extra(self) -> None:
        self.median = self.scale = self.mean = self.axes = None


class SmoothedDetector:
    """EWMA of another detector's score over `span` events; the EWMA level is part of the state."""

    def __init__(self, base, span: int = 5):
        self.base = base
        self.span = span
        self.alpha = 2.0 / (span + 1)
        self.level: float | None = None

    @property
    def hst_model(self):
        return getattr(self.base, "hst_model", self.base)

    def learn_one(self, x):
        self.base.learn_one(x)

    def score_one(self, x) -> float:
        # Smooth on the base detector's raw scale when it has one (PCA's unbounded SPE), then
        # bound: averaging already-squashed scores would compress exactly the large errors that
        # matter (measured on SMD: held-out PR-AUC 0.346 squashed-then-smoothed vs 0.398).
        raw = getattr(self.base, "raw_score", None)
        s = float(raw(x) if raw else self.base.score_one(x))
        self.level = s if self.level is None else self.alpha * s + (1 - self.alpha) * self.level
        return self.base.squash(self.level) if raw else self.level

    def squash(self, v: float) -> float:
        return self.base.squash(v) if hasattr(self.base, "squash") else v

    def unsquash(self, s: float) -> float:
        return self.base.unsquash(s) if hasattr(self.base, "unsquash") else s

    def prepare_calibration(self, fit_rows: list[dict], calib_rows: list[dict]) -> None:
        if hasattr(self.base, "prepare_calibration"):
            self.base.prepare_calibration(fit_rows, calib_rows)
        self.level = None  # calibration scores start a fresh average, as the prototype did

    def fingerprint(self) -> str:
        inner = self.base.fingerprint() if hasattr(self.base, "fingerprint") else "hst"
        return f"ewma{self.span}:{inner}"

    def extra_state(self) -> dict | None:
        inner = self.base.extra_state() if hasattr(self.base, "extra_state") else None
        return {"level": self.level, "inner": inner}

    def set_extra_state(self, state: dict | None) -> None:
        state = state or {}
        self.level = state.get("level")
        if hasattr(self.base, "set_extra_state"):
            self.base.set_extra_state(state.get("inner"))

    def clear_extra(self) -> None:
        self.level = None
        if hasattr(self.base, "clear_extra"):
            self.base.clear_extra()
