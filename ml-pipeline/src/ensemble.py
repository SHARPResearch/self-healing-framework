"""
ensemble.py — Component 1 v2: Half-Space Trees combined with a robust per-feature deviation score.

HST scores a point by how sparse its cell is in a random partition of the joint feature space.
In 38 dimensions a single metric spiking far outside its own normal range often still lands in a
populated cell, because the other 37 coordinates look normal. A per-feature robust z-score
(|x - median| / MAD, max over features) catches exactly that case and nothing else.

The two scores live on unrelated scales, so each is mapped to its percentile within its own
calibration scores and the two percentiles are combined, by mean (rank averaging) or by max.
Mean dilutes a strong single-scorer signal (a spike only one scorer sees lands mid-range); max
keeps it but gives normal points two chances to look extreme. The result is in [0, 1] either way
and is thresholded with the same per-entity percentile calibration as before, which absorbs the
difference in base rate. compare_detectors.py picks between them on the dev entities.

Lifecycle contract (used by src/lifecycle_manager.py and src/hst_state.py):
  learn_one / score_one       as any river detector; learning only updates the HST
  prepare_calibration(fit, calib)
                              fit the deviation scorer on `fit` rows and both reference score
                              distributions on frozen scores of `calib` rows; call it where a
                              plain model would compute its calibration scores
  extra_state / set_extra_state / clear_extra
                              the small non-HST state, carried inside HSTState snapshots
"""

import numpy as np

N_QUANTILES = 513  # reference distributions are stored as quantiles: constant size per version


class RobustDeviationScorer:
    """Max over features of |x - median| / (1.4826 MAD), median and MAD fixed at fit time."""

    def fit(self, rows: list[dict]) -> "RobustDeviationScorer":
        self.keys = list(rows[0])
        values = np.array([[r[k] for k in self.keys] for r in rows], dtype=float)
        self.median = np.median(values, axis=0)
        mad = np.median(np.abs(values - self.median), axis=0)
        # Flat features (MAD 0) fall back to the standard deviation, then to a tiny constant.
        self.scale = np.where(mad > 1e-9, 1.4826 * mad, values.std(axis=0) + 1e-6)
        return self

    def score(self, row: dict) -> float:
        x = np.fromiter((row[k] for k in self.keys), dtype=float, count=len(self.keys))
        return float(np.max(np.abs(x - self.median) / self.scale))


def _quantiles(values: list[float]) -> np.ndarray:
    return np.quantile(np.asarray(values, dtype=float), np.linspace(0, 1, N_QUANTILES))


def _percentile(ref: np.ndarray, value: float) -> float:
    return float(np.searchsorted(ref, value, side="right")) / len(ref)


class RankEnsembleDetector:
    def __init__(self, hst_model, combine: str = "mean"):
        if combine not in ("mean", "max"):
            raise ValueError(f"combine must be 'mean' or 'max', not {combine!r}")
        self.hst_model = hst_model     # a Pipeline(scaler, HST) or bare HST
        self.combine = combine
        self.dev: RobustDeviationScorer | None = None
        self.hst_ref: np.ndarray | None = None
        self.dev_ref: np.ndarray | None = None

    def learn_one(self, x):
        self.hst_model.learn_one(x)

    def _hst_score(self, x) -> float:
        return float(min(max(self.hst_model.score_one(x), 0.0), 1.0))

    def score_one(self, x):
        if self.dev is None:  # not calibrated yet: behave like the plain HST
            return self._hst_score(x)
        a = _percentile(self.hst_ref, self._hst_score(x))
        b = _percentile(self.dev_ref, self.dev.score(x))
        return max(a, b) if self.combine == "max" else (a + b) / 2

    def prepare_calibration(self, fit_rows: list[dict], calib_rows: list[dict]) -> None:
        self.dev = RobustDeviationScorer().fit(fit_rows)
        self.hst_ref = _quantiles([self._hst_score(r) for r in calib_rows])
        self.dev_ref = _quantiles([self.dev.score(r) for r in calib_rows])

    # ── snapshot support ─────────────────────────────────────────────────────
    def extra_state(self) -> dict | None:
        if self.dev is None:
            return None
        return {"keys": self.dev.keys, "median": self.dev.median.tolist(),
                "scale": self.dev.scale.tolist(), "hst_ref": self.hst_ref.tolist(),
                "dev_ref": self.dev_ref.tolist()}

    def set_extra_state(self, state: dict | None) -> None:
        if state is None:
            self.clear_extra()
            return
        dev = RobustDeviationScorer()
        dev.keys = state["keys"]
        dev.median = np.asarray(state["median"])
        dev.scale = np.asarray(state["scale"])
        self.dev = dev
        self.hst_ref = np.asarray(state["hst_ref"])
        self.dev_ref = np.asarray(state["dev_ref"])

    def clear_extra(self) -> None:
        self.dev = self.hst_ref = self.dev_ref = None
