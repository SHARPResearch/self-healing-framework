"""
lifecycle_manager.py — Component 2: Dynamic Model Updating for the HST anomaly detector.

DynamicModelManager owns one service's model for its whole life: calibrated warm-up, per-event
scoring, online learning, drift and change monitoring, and every lifecycle transition, each
versioned and audited through src/mlflow_lifecycle.py.

Policies (the same class runs all of them so the evaluation compares like with like):

  static          warm up once, never learn again (the proposal's static baseline).
  online          learn_one on every event, fixed threshold (plain river online learning).
  naive_rollback  online + ADWIN on the score stream; every drift restores the last stable
                  snapshot (the original Component 2 design, docs/Component_1_2_Technical_Guide.md
                  Part 5 and Doc1 §6).
  periodic        no learning between retrains; every `scheduled_every` steps rebuild the model
                  and recalibrate its threshold on the most recent window (the industry default
                  of scheduled retraining).
  gated           learn only from events the model does not flag (anomaly-gated updates, as in
                  MemStream-style poisoning defences). No lifecycle logic.
  cadal           Change-Aware Drift Attribution Lifecycle, the proposed method:
                    gated learning while stable, so incidents never teach the model;
                    three triggers open a quarantine (learning frozen, alerting continues):
                      drift   ADWIN (or Page-Hinkley/KSWIN) on the score stream,
                      event   an exogenous change (Kubernetes rollout),
                      time    a scheduled validity check of the champion's alarm rate;
                    at quarantine end a challenger is fitted on the buffered events and
                    src/drift_attribution.attribute() picks HOLD / PROMOTE / ROLLBACK / RESUME;
                    model *and* threshold are versioned together (a promoted model always
                    arrives with a threshold recalibrated on the new regime).

Challengers are trained in place on the champion's own (expensive to build) tree structure:
capture champion state (~30 ms), reset, fit, and either keep the result or re-apply the champion
state (~40 ms). See src/hst_state.py.
"""

import copy
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Iterable, Optional

import numpy as np

from src.change_events import ChangeEvent, ChangeEventSource, NullChangeEventSource
from src.config import HST_CFG, HSTConfig
from src.drift_attribution import (
    Action, Attribution, AttributionConfig, EarlyLookEvidence, QuarantineEvidence, Verdict,
    attribute, early_attribute,
)
from src.drift_detectors import ScoreDriftMonitor
from src.evaluate import pot_threshold
from src.hst_model import build_model, classify_severity, freeze_scaler
from src.hst_state import HSTState, apply, capture, reset
from src.mlflow_lifecycle import InMemoryRegistry
from src.publishers import EventPublisher, NullPublisher

logger = logging.getLogger(__name__)

POLICIES = ("static", "online", "naive_rollback", "periodic", "gated", "cadal")


@dataclass(frozen=True)
class LifecycleConfig:
    policy: str = "cadal"
    use_change_events: bool = True          # False = cadal ablation without the change prior
    calib_percentile: float = 97.0          # per-version threshold, see ml-pipeline/RESULTS.md
    # "percentile": threshold = calib_percentile of held-out scores. "pot": Peaks-Over-Threshold
    # extreme value fit at risk pot_q (src/evaluate.pot_threshold), selected on the SMD dev
    # entities for the PCA detector, where the percentile cut-off over-alarmed (RESULTS.md).
    threshold_method: str = "percentile"
    pot_q: float = 0.01
    # cadal learns only events scoring below this percentile of calibration scores. 0 (default)
    # disables continuous learning: the served model changes only through versioned, attributed,
    # validated transitions. On SMD every continuously learning variant lost recall, because
    # HST's sliding reference window absorbs long anomaly segments. A positive value (e.g. 75)
    # gives the gated-learning variant; gating on the alarm threshold itself would let a slowly
    # escalating incident creep into "normal" one just-below-threshold event at a time.
    learn_gate_percentile: float = 0.0
    detector: str = "adwin"
    adwin_delta: float = 0.002
    # Quarantine lengths (events). SMD is sampled once a minute, so 1440 = 1 day. Each must leave
    # the challenger's fit slice >= HST window_size or it cannot score at all. A shorter buffer
    # after a change event was tried (720) and made challengers too noisy to pass the
    # stationarity test on SMD; the change prior now acts through the immediate trigger, the
    # quarantine restart and the lower persistence requirement instead.
    quarantine_with_change: int = 1440
    quarantine_silent: int = 1440
    change_horizon: int = 720               # a change explains a shift whose quarantine opens within this many steps after it
    fit_frac: float = 0.5                   # quarantine buffer split: fit / calib / tail
    calib_frac: float = 0.3
    # Sequential early stop (drift_attribution.early_attribute): look at the buffer part-way
    # through and decide early only when an exact bound makes the outcome conclusive; otherwise
    # the full-length decision runs unchanged. Off by default so the published runs reproduce.
    early_stop: bool = False
    early_looks: tuple[float, ...] = (0.5, 0.75)   # fractions of the quarantine length
    early_alpha: float = 0.05               # one-sided error per look and rule (~0.1 per rule over 2 looks)
    cooldown: int = 250                     # ignore drift signals right after a decision
    scheduled_every: int = 2880             # time trigger + checkpoint cadence (2 days)
    scheduled_window: int = 720             # alarm-rate window for the scheduled validity check
    periodic_window: int = 1440             # training window for the periodic policy
    naive_stable_every: int = 1000          # naive_rollback stable-snapshot cadence (guide Part 5)
    attribution: AttributionConfig = field(default_factory=AttributionConfig)
    null_windows: int = 8                   # training windows per quarantine length (0 disables)
    null_quantile: float = 0.9              # normal windows pass the stationarity test this often
    # Re-baselining (cadal): a metric whose robust median moved by more than this many of its
    # reference robust standard deviations is shifted back onto the champion's baseline.
    rebaseline: bool = True
    rebaseline_k: float = 3.0
    # Evaluate closed quarantines on a copy of the champion in a background thread while the
    # champion keeps scoring (FR3). Off by default so evaluation runs are deterministic. Copying
    # is cheap only for lazy trees (HST_LAZY); river's eager trees copy ~1.6M nodes.
    async_decisions: bool = False
    # Operator in the loop (CADAL-HITL). When the label-free evidence cannot settle a shift (a
    # self-consistent new regime with no change event to explain it), ask the operator instead of
    # guessing: the champion keeps serving, the validated challenger waits as a pending candidate,
    # and the answer licenses or refuses its promotion. Unanswered queries expire to HOLD.
    operator_queries: bool = False
    query_ttl: int = 1440                   # events a query stays open before falling back to HOLD
    query_budget: int = 2                   # at most this many queries per service ...
    query_budget_window: int = 1440         # ... per this many events (one day at SMD rate)
    query_cooldown: int = 1440              # after "incident", do not ask again for this long

    def __post_init__(self):
        if self.policy not in POLICIES:
            raise ValueError(f"Unknown policy {self.policy!r}, expected one of {POLICIES}")

    def for_sampling(self, samples_per_day: float) -> "LifecycleConfig":
        """
        The same lifecycle at a different sampling rate.

        Every length above is defined for SMD's one sample per minute (1440 per day). This
        rescales them all by samples_per_day / 1440 so that "a day of evidence" still means a day
        on, say, NAB's five-minute series, without per-dataset tuning. Pair with
        hst_window_for_sampling() so the challenger's fit slice still covers an HST window.
        """
        k = samples_per_day / 1440.0
        scale = lambda n: max(1, int(round(n * k)))  # noqa: E731
        return replace(
            self,
            quarantine_with_change=scale(self.quarantine_with_change),
            quarantine_silent=scale(self.quarantine_silent),
            change_horizon=scale(self.change_horizon),
            query_ttl=scale(self.query_ttl),
            query_budget_window=scale(self.query_budget_window),
            query_cooldown=scale(self.query_cooldown),
            cooldown=scale(self.cooldown),
            scheduled_every=scale(self.scheduled_every),
            scheduled_window=scale(self.scheduled_window),
            periodic_window=scale(self.periodic_window),
            naive_stable_every=scale(self.naive_stable_every),
        )

    @property
    def learns_while_serving(self) -> bool:
        """Whether the served model keeps learning between versions (decides how to calibrate)."""
        if self.policy == "cadal":
            return self.learn_gate_percentile > 0
        return self.policy not in ("static", "periodic")

    @property
    def target_rate(self) -> float:
        """Alarm rate the threshold is designed to produce on normal data (r0 in attribution)."""
        if self.threshold_method == "pot":
            return self.pot_q
        return 1.0 - self.calib_percentile / 100.0


@dataclass
class StepResult:
    step: int
    score: float
    alarm: bool
    severity: str
    threshold: float
    version: int
    phase: str                  # "stable" | "quarantine"
    latency_ms: float
    lifecycle: Optional[dict] = None   # set on the step a lifecycle decision was taken


def _clamp(x: float) -> float:
    return float(min(max(x, 0.0), 1.0))


def robust_stats(rows: list[dict]) -> dict[str, tuple[float, float]]:
    """Per-feature (median, robust standard deviation = 1.4826 MAD, falling back to std)."""
    keys = list(rows[0])
    values = np.array([[r[k] for k in keys] for r in rows], dtype=float)
    med = np.median(values, axis=0)
    mad = 1.4826 * np.median(np.abs(values - med), axis=0)
    scale = np.where(mad > 1e-9, mad, values.std(axis=0))
    return {k: (float(m), float(max(sc, 1e-6))) for k, m, sc in zip(keys, med, scale)}


def fit_rebaseline(ref: dict, rows: list[dict], k: float) -> dict[str, float]:
    """
    Level shifts that map `rows` back onto the reference baseline: for every feature whose median
    moved by more than k reference robust standard deviations, the offset to subtract.
    """
    new = robust_stats(rows)
    return {
        f: round(new[f][0] - m, 6)
        for f, (m, sc) in ref.items()
        if f in new and abs(new[f][0] - m) > k * sc
    }


def rebaselined(x: dict, shifts: dict[str, float]) -> dict:
    if not shifts:
        return x
    return {f: (v - shifts[f] if f in shifts else v) for f, v in x.items()}


def calibrated_threshold(model, calib_scores: list[float], cfg: "LifecycleConfig") -> float:
    """
    Alarm threshold for one model version from its held-out calibration scores. POT fits the tail
    on the detector's raw scale when it has one (PCA's unbounded error), then maps back.
    """
    if cfg.threshold_method == "pot":
        unsquash = getattr(model, "unsquash", None)
        squash = getattr(model, "squash", None)
        raw = [unsquash(s) for s in calib_scores] if unsquash else list(calib_scores)
        t = pot_threshold(raw, cfg.pot_q)
        return float(squash(t)) if squash else float(t)
    return float(np.percentile(calib_scores, cfg.calib_percentile))


def prepare_calibration(model, fit_rows: list[dict], calib_rows: list[dict]) -> None:
    """Let a wrapper detector (src/ensemble.py) fit its calibration state; no-op for plain HST."""
    if hasattr(model, "prepare_calibration"):
        model.prepare_calibration(fit_rows, calib_rows)


def hst_window_for_sampling(samples_per_day: float, base_window: int = 250) -> int:
    """HST window scaled like LifecycleConfig.for_sampling (250 events at 1440 per day)."""
    return max(25, int(round(base_window * samples_per_day / 1440.0)))


def attribution_null(mgr: "DynamicModelManager", train_rows: list[dict]) -> dict[int, dict[str, float]]:
    """
    Per-entity null distribution of the stationarity test, from normal training data.

    For each quarantine length the manager can use, run the exact quarantine test
    (DynamicModelManager.stationarity_test) on `null_windows` evenly spaced windows of the
    training split and keep the `null_quantile` of the challenger tail alarm rate and of the
    out-of-support rate. Attribution then only calls a regime unlearnable or moving when it is
    worse than this entity's own normal behaviour usually looks. The model is restored after.
    """
    cfg = mgr.cfg
    if cfg.null_windows <= 0:
        return {}
    saved = capture(mgr.model)
    null = {}
    for length in sorted({cfg.quarantine_with_change, cfg.quarantine_silent}):
        if len(train_rows) < 2 * length:
            continue
        starts = np.linspace(0, len(train_rows) - length, cfg.null_windows).astype(int)
        rates, moving = zip(*(mgr.stationarity_test(train_rows[s:s + length]) for s in starts))
        null[length] = {
            "learnable": float(np.quantile(rates, cfg.null_quantile)),
            "moving": float(np.quantile(moving, cfg.null_quantile)),
        }
    apply(mgr.model, saved)
    return null


def out_of_support_rate(fit_rows: list[dict], rows: list[dict], margin: float = 0.1) -> float:
    """
    How persistently the most-moving feature has left the range seen in `fit_rows`.

    For each feature, the fraction of `rows` outside its fitted [min, max] widened by `margin` x
    that range (with a small absolute floor for flat features); returns the maximum over
    features. Transient spikes in a few of many features stay low; a feature that is trending
    away (runaway metric, memory leak) is out of support for most of the tail.
    """
    keys = list(fit_rows[0])
    worst = 0
    for k in keys:
        values = [r[k] for r in fit_rows]
        lo, hi = min(values), max(values)
        pad = max(margin * (hi - lo), 1e-3)
        worst = max(worst, sum(1 for r in rows if r[k] < lo - pad or r[k] > hi + pad))
    return worst / len(rows)


class DynamicModelManager:
    def __init__(
        self,
        service_id: str,
        cfg: LifecycleConfig = LifecycleConfig(),
        hst_cfg: HSTConfig = HST_CFG,
        registry: Optional[InMemoryRegistry] = None,
        change_source: Optional[ChangeEventSource] = None,
        publisher: Optional[EventPublisher] = None,
        model=None,
    ):
        self.service_id = service_id
        self.cfg = cfg
        self.hst_cfg = hst_cfg
        self.model = model if model is not None else build_model(hst_cfg)
        self.registry = registry or InMemoryRegistry(service_id)
        self.changes = change_source or NullChangeEventSource()
        self.publisher = publisher or NullPublisher()
        self.monitor = ScoreDriftMonitor(cfg.detector, cfg.adwin_delta)

        self.threshold = 1.0
        self.learn_gate = 1.0
        self.step = 0
        self.phase = "stable"
        self._cooldown_until = 0
        self._last_change: Optional[ChangeEvent] = None
        self._last_change_step = -10**9
        self._recent_alarms: deque[bool] = deque(maxlen=cfg.scheduled_window)
        self._recent_rows: deque[dict] = deque(maxlen=cfg.periodic_window)
        self._recent_scores: deque[float] = deque(maxlen=cfg.naive_stable_every)
        self._last_checkpoint_step = 0

        # Quarantine state
        self._q_rows: list[dict] = []
        self._q_alarms: list[bool] = []
        self._q_trigger = ""
        self._q_target_len = 0
        self._q_start = 0
        self._q_looks: list[int] = []           # buffer lengths at which to try an early decision

        self.decisions: list[dict] = []
        self.attribution_null: dict[int, dict[str, float]] = {}
        # Re-baselining state, versioned with the model (HSTState.meta): the robust stats of the
        # data the served model was fitted on, and the per-metric shifts currently applied.
        self.ref_stats: Optional[dict[str, tuple[float, float]]] = None
        self.shifts: dict[str, float] = {}
        self.transition_ms: list[float] = []   # time the serving loop was blocked by a transition
        self.decision_ms: list[float] = []     # time spent evaluating quarantines (any thread)
        self._executor: Optional[ThreadPoolExecutor] = None
        self._pending = None
        self._pending_kind = ""                 # "decision" (closes the quarantine) or "look" (may not)
        self._deferred_change = False
        # Operator queries: query_id -> record; pending candidates stay in memory only.
        self.queries: dict[str, dict] = {}
        self._query_steps: list[int] = []
        self._ask_cooldown_until = 0

    # ── warm-up ──────────────────────────────────────────────────────────────
    def warm_up(self, rows: list[dict], calib_frac: float = 0.2) -> dict:
        """
        Calibrated warm-up (same split as src.pipeline.warm_up_calibrate_and_score): learn the
        first 80%, set the threshold at `calib_percentile` of scores on the held-out last 20%,
        then learn that 20% too. Registers the result as production version 1.

        Policies that keep learning while serving are calibrated prequentially (score each
        held-out row, then learn it), frozen policies on frozen scores: calibrate the way the
        model will be served.
        """
        start = time.perf_counter()
        split = int(len(rows) * (1 - calib_frac))
        for r in rows[:split]:
            self.model.learn_one(r)
        prepare_calibration(self.model, rows[:split], rows[split:])
        frozen = [_clamp(self.model.score_one(r)) for r in rows[split:]]
        prequential = self._prequential(rows[split:])
        freeze_scaler(self.model)
        calib_scores = prequential if self.cfg.learns_while_serving else frozen
        null = attribution_null(self, rows) if self.cfg.policy == "cadal" else {}
        self.start_from(None, calib_scores, rows[-self.cfg.periodic_window:], null,
                        ref_stats=robust_stats(rows[:split]))
        duration = time.perf_counter() - start
        return {"events": len(rows), "duration_s": round(duration, 2), "threshold": self.threshold}

    def start_from(self, state: Optional[HSTState], calib_scores: list[float],
                   recent_rows: list[dict], null: Optional[dict] = None,
                   ref_stats: Optional[dict] = None) -> None:
        """
        Begin serving from an already warmed-up state (None = the model as it is now).

        Lets many policies or replicas share one expensive warm-up: apply the warm state to a
        structurally identical model, calibrate from the same held-out scores, register v1.
        """
        if state is not None:
            apply(self.model, state)
        self.attribution_null = dict(null or {})
        self.ref_stats = dict(ref_stats) if ref_stats else None
        self.shifts = {}
        self.threshold, self.learn_gate = self._calibrate(calib_scores)
        self._recent_rows.extend(recent_rows)
        version = self.registry.register(
            self._snapshot(), self.threshold, self.cfg.target_rate,
            step=0, reason="calibrated warm-up on training split",
            tags={"kind": "warm_up", "learn_gate": self.learn_gate},
        )
        self.registry.set_production(version, step=0, transition="promote",
                                     reason="initial production model after warm-up")

    # ── per-event ────────────────────────────────────────────────────────────
    def process(self, x: dict) -> StepResult:
        t0 = time.perf_counter()
        self.step += 1
        decision = None

        if self._pending is not None and self._pending.done():
            decision = self._take_pending(self._pending.result())

        decision = self._expire_queries() or decision

        for evt in self.changes.poll(self.step):
            decision = self._on_change_event(evt) or decision

        v = rebaselined(x, self.shifts)
        score = _clamp(self.model.score_one(v))
        alarm = score >= self.threshold
        self._recent_alarms.append(alarm)
        self._recent_rows.append(x)
        self._recent_scores.append(score)

        policy = self.cfg.policy
        if policy == "online":
            self.model.learn_one(v)
        elif policy == "gated":
            if not alarm:
                self.model.learn_one(v)
        elif policy == "naive_rollback":
            decision = self._naive_rollback_step(x, score) or decision
        elif policy == "periodic":
            if self.step % self.cfg.scheduled_every == 0:
                decision = self._periodic_retrain()
        elif policy == "cadal":
            decision = self._cadal_step(x, v, score, alarm) or decision

        return StepResult(
            step=self.step, score=score, alarm=alarm, severity=classify_severity(score),
            threshold=self.threshold, version=self.registry.production_version or 0,
            phase=self.phase, latency_ms=(time.perf_counter() - t0) * 1000, lifecycle=decision,
        )

    def run(self, rows: Iterable[dict]) -> Iterable[StepResult]:
        for x in rows:
            yield self.process(x)

    # ── policies ─────────────────────────────────────────────────────────────
    def _naive_rollback_step(self, x: dict, score: float) -> Optional[dict]:
        self.model.learn_one(x)
        signal = self.monitor.update(score, self.step)
        if self.step % self.cfg.naive_stable_every == 0:
            mean = sum(self._recent_scores) / len(self._recent_scores)
            if mean < self.threshold:
                self._checkpoint(f"rolling mean score {mean:.4f} below threshold")
        if signal is None:
            return None
        t = time.perf_counter()
        target = self.registry.production()
        self._restore(target.state)
        self.registry.set_production(
            target.version, step=self.step, transition="rollback",
            reason=f"ADWIN drift ({signal.direction}) triggers unconditional rollback",
            evidence={"direction": signal.direction, "mean_before": signal.mean_before,
                      "mean_after": signal.mean_after},
        )
        self.transition_ms.append((time.perf_counter() - t) * 1000)
        return self._decide({"action": "rollback", "verdict": "unattributed", "trigger": "drift_" + signal.direction})

    def _calibrate(self, calib_scores: list[float]) -> tuple[float, float]:
        """(alarm threshold, learning gate) from held-out scores of one model version."""
        threshold = calibrated_threshold(self.model, calib_scores, self.cfg)
        gate_pct = self.cfg.learn_gate_percentile
        gate = float(np.percentile(calib_scores, gate_pct)) if gate_pct > 0 else -1.0
        return threshold, min(gate, threshold)

    def _prequential(self, rows: list[dict], model=None) -> list[float]:
        """Score each row, then learn it: the way a serving model sees the stream."""
        model = self.model if model is None else model
        scores = []
        for r in rows:
            scores.append(_clamp(model.score_one(r)))
            model.learn_one(r)
        return scores

    def stationarity_test(self, rows: list[dict]) -> tuple[float, float]:
        """
        The quarantine's label-free stationarity test on one buffer, run on the model in place:
        fit a challenger on the first part, calibrate on the middle, return (challenger tail
        alarm rate, tail out-of-support rate). Leaves the model holding the challenger.
        """
        n = len(rows)
        n_fit, n_calib = int(n * self.cfg.fit_frac), int(n * self.cfg.calib_frac)
        threshold, _ = self._fit_challenger(rows[:n_fit], rows[n_fit:n_fit + n_calib])
        tail = rows[n_fit + n_calib:]
        rate = sum(_clamp(self.model.score_one(r)) >= threshold for r in tail) / len(tail)
        return rate, out_of_support_rate(rows[:n_fit], tail)

    def _fit_challenger(self, rows: list[dict], calib_rows: list[dict], model=None) -> tuple[float, float]:
        """
        Reset the model in place, learn `rows`, return (threshold, gate) calibrated on frozen
        scores of `calib_rows`. The caller decides whether the model then learns `calib_rows`.
        """
        model = self.model if model is None else model
        reset(model, keep_scaler=True)
        for r in rows:
            model.learn_one(r)
        prepare_calibration(model, rows, calib_rows)
        return self._calibrate([_clamp(model.score_one(r)) for r in calib_rows])

    def _checkpoint(self, reason: str) -> None:
        t = time.perf_counter()
        self.registry.checkpoint(self._snapshot(), self.threshold, self.cfg.target_rate,
                                 step=self.step, reason=reason,
                                 tags={"kind": "stable_checkpoint", "learn_gate": self.learn_gate})
        self.transition_ms.append((time.perf_counter() - t) * 1000)

    def _periodic_retrain(self) -> dict:
        t = time.perf_counter()
        rows = list(self._recent_rows)
        split = int(len(rows) * 0.8)
        # periodic serves a frozen model between retrains, so frozen calibration matches serving
        self.threshold, self.learn_gate = self._fit_challenger(rows[:split], rows[split:])
        for r in rows[split:]:
            self.model.learn_one(r)
        version = self.registry.register(self._snapshot(), self.threshold, self.cfg.target_rate,
                                         step=self.step, reason="scheduled retrain on recent window")
        self.registry.set_production(version, step=self.step, transition="promote",
                                     reason="scheduled retrain (unconditional)")
        self.transition_ms.append((time.perf_counter() - t) * 1000)
        return self._decide({"action": "promote", "verdict": "scheduled", "trigger": "scheduled"})

    def _change_in_horizon(self, since: Optional[int] = None) -> Optional[str]:
        """
        Id of a change event that explains a shift observed from step `since` (default: now):
        one that happened at most `change_horizon` steps before it, or any time after it (a
        change during the quarantine explains what the quarantine observed).
        """
        if not self.cfg.use_change_events or self._last_change is None:
            return None
        since = self.step if since is None else since
        if self._last_change_step >= since - self.cfg.change_horizon:
            return self._last_change.event_id
        return None

    def _on_change_event(self, evt: ChangeEvent) -> Optional[dict]:
        if self.cfg.policy != "cadal" or not self.cfg.use_change_events:
            return None
        self._last_change, self._last_change_step = evt, self.step
        self.publisher.publish_lifecycle({"service_id": self.service_id, "event": "change_observed",
                                          "change_event_id": evt.event_id, "step": self.step})
        # Evidence about the post-change regime has to come from after the change, so a change
        # during an open quarantine restarts it rather than reusing the pre-change buffer. While
        # an asynchronous decision is in flight, the new quarantine opens once it is applied.
        if self.phase == "deciding":
            self._deferred_change = True
            return None
        self._open_quarantine("change_event")
        return None

    def _open_quarantine(self, trigger: str) -> None:
        self.phase = "quarantine"
        self._q_start = self.step
        self._q_trigger = trigger
        self._q_rows, self._q_alarms = [], []
        explained = trigger == "change_event" or self._change_in_horizon() is not None
        self._q_target_len = self.cfg.quarantine_with_change if explained else self.cfg.quarantine_silent
        self._q_looks = sorted({int(round(f * self._q_target_len)) for f in self.cfg.early_looks
                                if 0 < f < 1}) if self.cfg.early_stop else []
        self.publisher.publish_lifecycle({"service_id": self.service_id, "event": "quarantine_opened",
                                          "trigger": trigger, "step": self.step,
                                          "length": self._q_target_len})

    def _cadal_step(self, x: dict, v: dict, score: float, alarm: bool) -> Optional[dict]:
        if score < self.learn_gate:
            self.model.learn_one(v)                 # gated learning: only clearly typical events teach

        if self.phase == "deciding":  # an asynchronous decision is in flight: just keep serving
            return None
        if self.phase == "quarantine":
            self._q_rows.append(x)
            self._q_alarms.append(alarm)
            self.monitor.update(score, self.step)
            if len(self._q_rows) >= self._q_target_len:
                return self._close_quarantine()
            if len(self._q_rows) in self._q_looks and self._pending is None:
                return self._early_look()
            return None
        signal = self.monitor.update(score, self.step)
        if signal is not None and self.step >= self._cooldown_until:
            self._open_quarantine("drift_" + signal.direction)
            return None

        if self.step % self.cfg.scheduled_every == 0:
            rate = sum(self._recent_alarms) / len(self._recent_alarms)
            stale = self.cfg.attribution.stale_factor_silent * self.cfg.target_rate
            if rate >= stale:
                self._open_quarantine("scheduled")
            else:
                self._checkpoint(f"scheduled validity check passed (alarm rate {rate:.4f})")
        return None

    def _quarantine_context(self) -> dict:
        """Everything the quarantine decision needs, frozen at the moment the quarantine closes."""
        n = len(self._q_rows)
        return {
            "rows": list(self._q_rows), "alarms": list(self._q_alarms), "trigger": self._q_trigger,
            "change_event_id": self._change_in_horizon(since=self._q_start),
            "champion_state": capture(self.model),
            "champion_threshold": self.threshold, "champion_gate": self.learn_gate,
            "ref_stats": self.ref_stats, "null": self.attribution_null.get(n, {}),
            "may_ask": self._may_ask(), "q_start": self._q_start, "length": self._q_target_len,
        }

    def quarantine_progress(self) -> Optional[dict]:
        """How far the open quarantine is (events seen of its length, early-look points), or None."""
        if self.phase == "stable":
            return None
        return {"seen": len(self._q_rows), "length": self._q_target_len, "looks": list(self._q_looks)}

    def _may_ask(self) -> bool:
        # One open question per service at a time: while the operator has not answered, a new
        # ambiguous shift is held like before rather than stacking a second query.
        if not self.cfg.operator_queries or self.step < self._ask_cooldown_until or self.open_queries:
            return False
        recent = [s for s in self._query_steps if self.step - s < self.cfg.query_budget_window]
        return len(recent) < self.cfg.query_budget

    def _rebaseline_tail(self, model, ctx: dict, fit_rows: list[dict],
                         tail_rows: list[dict]) -> tuple[dict, Optional[int]]:
        """Shifts fitted on `fit_rows`, and how many tail events the re-baselined champion flags."""
        if not (self.cfg.policy == "cadal" and self.cfg.rebaseline and ctx["ref_stats"]):
            return {}, None
        shifts = fit_rebaseline(ctx["ref_stats"], fit_rows, self.cfg.rebaseline_k)
        if not shifts:
            return {}, None
        threshold = ctx["champion_threshold"]
        return shifts, sum(_clamp(model.score_one(rebaselined(r, shifts))) >= threshold for r in tail_rows)

    def _early_look(self) -> Optional[dict]:
        """Try to decide the quarantine now; a look that is not conclusive leaves it collecting."""
        ctx = self._quarantine_context()
        if not self.cfg.async_decisions:
            out = self._evaluate_early(self.model, ctx)
            out["blocked_ms"] = out["eval_ms"]
            return self._take_look(out)
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"cadal-{self.service_id}")
        self._pending_kind = "look"             # keep collecting while it runs: phase stays quarantine
        self._pending = self._executor.submit(self._evaluate_early, copy.deepcopy(self.model), ctx)
        return None

    def _evaluate_early(self, model, ctx: dict) -> dict:
        """The early-look evidence (drift_attribution.early_attribute) on `model` as scratch space."""
        t0 = time.perf_counter()
        rows, alarms = ctx["rows"], ctx["alarms"]
        m = len(rows)
        n_fit = int(m * self.cfg.fit_frac)
        # Re-baselining keeps the champion's own threshold, so unlike a challenger it needs no
        # calibration slice: every event after the fit slice is held out from it and tests it.
        tail_rows, tail_alarms = rows[n_fit:], alarms[n_fit:]
        recent = alarms[m // 2:]
        new_shifts, rebaseline_alarms = self._rebaseline_tail(model, ctx, rows[:n_fit], tail_rows)
        apply(model, ctx["champion_state"])     # scoring advanced the smoothing state; undo it
        evidence = EarlyLookEvidence(
            trigger=ctx["trigger"], target_rate=self.cfg.target_rate, n_seen=m, n_full=ctx["length"],
            recent_alarms=sum(recent), n_recent=len(recent),
            tail_alarms=sum(tail_alarms), n_tail=len(tail_rows),
            n_tail_full=ctx["length"] - int(ctx["length"] * self.cfg.fit_frac)
            - int(ctx["length"] * self.cfg.calib_frac),
            change_event_id=ctx["change_event_id"], rebaseline_tail_alarms=rebaseline_alarms,
            tail_out_of_support_rate=out_of_support_rate(rows[:n_fit], tail_rows),
            moving_floor=self.attribution_null.get(ctx["length"], {}).get("moving"),
        )
        result = early_attribute(evidence, self.cfg.attribution, self.cfg.early_alpha)
        return {
            **ctx, "look": True, "result": result, "new_shifts": new_shifts, "rollback_target": None,
            "challenger_state": None, "challenger_threshold": None, "challenger_gate": None,
            "new_ref_stats": None, "eval_ms": (time.perf_counter() - t0) * 1000,
        }

    def _take_look(self, out: dict) -> Optional[dict]:
        """Apply an early look's outcome if it is conclusive and still about the open quarantine."""
        current = self.phase == "quarantine" and out["q_start"] == self._q_start
        conclusive = current and out["result"] is not None
        if current:
            self.publisher.publish_lifecycle({
                "service_id": self.service_id, "event": "quarantine_look", "step": self.step,
                "seen": len(out["rows"]), "length": out["length"], "conclusive": conclusive,
                "verdict": out["result"].verdict.value if conclusive else None,
                "action": out["result"].action.value if conclusive else None,
            })
        return self._apply_outcome(out) if conclusive else None

    def _take_pending(self, out: dict) -> Optional[dict]:
        kind, self._pending, self._pending_kind = self._pending_kind, None, ""
        return self._take_look(out) if kind == "look" else self._apply_outcome(out)

    def _evaluate_quarantine(self, model, ctx: dict) -> dict:
        """
        Decide what the quarantine observed, using `model` as scratch space.

        `model` starts as the champion and may be left holding the challenger. Nothing here
        touches the served model, writes the registry or publishes, so it can run on a copy of the
        champion in a background thread (async_decisions) while scoring continues.
        """
        t0 = time.perf_counter()
        rows, alarms = ctx["rows"], ctx["alarms"]
        n = len(rows)
        n_fit = int(n * self.cfg.fit_frac)
        n_calib = int(n * self.cfg.calib_frac)
        tail_rows, tail_alarms = rows[n_fit + n_calib:], alarms[n_fit + n_calib:]
        champion_threshold = ctx["champion_threshold"]

        # Repair 1, re-baselining: keep the champion, shift the metrics whose level moved back
        # onto its baseline (estimated on the fit slice), and see whether it then finds the tail
        # normal again with its own threshold. Measured before the challenger touches the model.
        new_shifts, rebaseline_alarms = self._rebaseline_tail(model, ctx, rows[:n_fit], tail_rows)
        rebaseline_tail = None if rebaseline_alarms is None else rebaseline_alarms / len(tail_rows)

        # Repair 2, retraining: a challenger fitted on the new regime alone. Learnability is a
        # stationarity test, so it is measured frozen: fitted on the start of the buffer,
        # calibrated on the middle, does the model still find the tail normal? A new steady
        # regime passes; a trend or an escalating incident drifts away from the fit.
        challenger_threshold, challenger_gate = self._fit_challenger(
            rows[:n_fit], rows[n_fit:n_fit + n_calib], model)
        challenger_tail = (
            sum(_clamp(model.score_one(r)) >= challenger_threshold for r in tail_rows) / len(tail_rows)
        )
        evidence = QuarantineEvidence(
            trigger=ctx["trigger"],
            target_rate=self.cfg.target_rate,
            champion_alarm_rate=sum(alarms) / n,
            champion_tail_alarm_rate=sum(tail_alarms) / len(tail_alarms),
            challenger_tail_alarm_rate=challenger_tail,
            change_event_id=ctx["change_event_id"],
            n_tail=len(tail_rows),
            tail_out_of_support_rate=out_of_support_rate(rows[:n_fit], tail_rows),
            learnable_floor=ctx["null"].get("learnable"),
            moving_floor=ctx["null"].get("moving"),
            rebaseline_tail_alarm_rate=rebaseline_tail,
        )
        attribution_cfg = replace(self.cfg.attribution, ask_operator=ctx.get("may_ask", False))
        result: Attribution = attribute(evidence, attribution_cfg)

        rollback_target = None
        if result.action is Action.ROLLBACK:
            rollback_target = self.registry.previous_production() or self.registry.production()
            target_rate = self._alarm_rate_of(rollback_target, tail_rows, model)
            healthy = (self.cfg.attribution.decay_factor * self.cfg.target_rate <= target_rate
                       < self.cfg.attribution.rollback_max_alarm_rate)
            result.evidence["rollback_target_version"] = rollback_target.version
            result.evidence["rollback_target_tail_alarm_rate"] = round(target_rate, 4)
            if not healthy:
                result = Attribution(
                    Verdict.NO_CHANGE, Action.RESUME,
                    f"{result.reason}; but rollback target v{rollback_target.version} does not fit "
                    f"recent data either (tail alarm rate {target_rate:.4f}), keeping the champion",
                    result.evidence,
                )

        challenger_state = None
        if result.action in (Action.PROMOTE, Action.ASK) and result.evidence.get("repair") != "rebaseline":
            if self.cfg.learns_while_serving:
                # A learning model is served with a threshold calibrated the way it will run
                # (score each remaining buffered event, then learn it), not on the frozen
                # stationarity test.
                challenger_threshold, challenger_gate = self._calibrate(
                    self._prequential(rows[n_fit:], model))
            # A frozen-serving promotion serves exactly what was validated: the challenger
            # fitted on the fit slice with the threshold from frozen scores of the calib slice.
            challenger_state = capture(model)
        return {
            **ctx,
            "result": result, "new_shifts": new_shifts, "rollback_target": rollback_target,
            "challenger_state": challenger_state, "challenger_threshold": challenger_threshold,
            "challenger_gate": challenger_gate, "new_ref_stats": robust_stats(rows[:n_fit]),
            "eval_ms": (time.perf_counter() - t0) * 1000,
        }

    def _apply_outcome(self, out: dict) -> dict:
        """Serve what the evaluation decided. Runs on the serving thread, in milliseconds."""
        t = time.perf_counter()
        result = out["result"]
        result.evidence.setdefault("early", False)
        result.evidence.setdefault("quarantine_events", len(out["rows"]))
        result.evidence.setdefault("quarantine_length", out.get("length"))
        if result.action is Action.PROMOTE and result.evidence.get("repair") == "rebaseline":
            # The champion is served again, unchanged, behind the new input shifts.
            apply(self.model, out["champion_state"])
            self.threshold, self.learn_gate = out["champion_threshold"], out["champion_gate"]
            self.shifts = out["new_shifts"]
            result.evidence["rebaselined"] = out["new_shifts"]
            version = self.registry.register(
                self._snapshot(), self.threshold, self.cfg.target_rate, step=self.step,
                reason=result.reason, tags={"kind": "rebaseline", "verdict": result.verdict.value,
                                            "learn_gate": self.learn_gate,
                                            "n_rebaselined": len(out["new_shifts"])},
            )
            self.registry.set_production(version, step=self.step, transition="promote",
                                         reason=result.reason, evidence=result.evidence)
        elif result.action is Action.PROMOTE:
            # The challenger now defines "normal": its own fit data is the new reference.
            apply(self.model, out["challenger_state"])
            self.shifts = {}
            self.ref_stats = out["new_ref_stats"]
            self.threshold, self.learn_gate = out["challenger_threshold"], out["challenger_gate"]
            version = self.registry.register(
                self._snapshot(), self.threshold, self.cfg.target_rate, step=self.step,
                reason=result.reason, tags={"kind": "challenger", "verdict": result.verdict.value,
                                            "learn_gate": self.learn_gate},
            )
            self.registry.set_production(version, step=self.step, transition="promote",
                                         reason=result.reason, evidence=result.evidence)
        elif result.action is Action.ROLLBACK:
            target = out["rollback_target"]
            self._restore(target.state)
            self.threshold = target.threshold
            self.learn_gate = target.tags.get("learn_gate", target.threshold)
            self.registry.set_production(target.version, step=self.step, transition="rollback",
                                         reason=result.reason, evidence=result.evidence)
        else:  # HOLD, RESUME or ASK: the champion stays, exactly as it was
            apply(self.model, out["champion_state"])
            self.threshold, self.learn_gate = out["champion_threshold"], out["champion_gate"]

        query_id = None
        if result.action is Action.ASK:
            query_id = self._open_query(result, out)

        self.monitor.reset()
        self.phase = "stable"
        self._cooldown_until = self.step + self.cfg.cooldown
        self.transition_ms.append(out.get("blocked_ms", 0.0) + (time.perf_counter() - t) * 1000)
        self.decision_ms.append(out["eval_ms"])
        decision = self._decide({"action": result.action.value, "verdict": result.verdict.value,
                                 "trigger": out["trigger"], "reason": result.reason,
                                 "evidence": result.evidence, "query_id": query_id})
        if self._deferred_change:
            self._deferred_change = False
            self._open_quarantine("change_event")
        return decision

    # -- operator in the loop -------------------------------------------------------------------
    def _open_query(self, result: Attribution, out: dict) -> str:
        query_id = f"q-{self.service_id}-{self.step}"
        self._query_steps.append(self.step)
        self.queries[query_id] = {
            "query_id": query_id, "service_id": self.service_id, "status": "open",
            "created_step": self.step, "expires_step": self.step + self.cfg.query_ttl,
            "question": "Is this a new normal for the service, or an incident?",
            "reason": result.reason, "evidence": result.evidence,
            "answer": None, "operator": None, "answered_step": None,
            "_candidate": {
                "state": out["challenger_state"], "threshold": out["challenger_threshold"],
                "gate": out["challenger_gate"], "ref_stats": out["new_ref_stats"],
            },
        }
        self.publisher.publish_lifecycle({"event": "operator_query", **self.public_query(query_id)})
        return query_id

    def public_query(self, query_id: str) -> dict:
        """A query without its in-memory candidate model, for APIs and events."""
        return {k: v for k, v in self.queries[query_id].items() if not k.startswith("_")}

    @property
    def open_queries(self) -> list[dict]:
        return [self.public_query(q) for q, r in self.queries.items() if r["status"] == "open"]

    def _expire_queries(self) -> Optional[dict]:
        decision = None
        for query_id, q in self.queries.items():
            if q["status"] == "open" and self.step >= q["expires_step"]:
                q["status"] = "expired"
                q.pop("_candidate", None)
                # An unanswered question is not re-asked straight away either (alert fatigue).
                self._ask_cooldown_until = max(self._ask_cooldown_until, self.step + self.cfg.query_cooldown)
                self.publisher.publish_lifecycle({"event": "query_expired", **self.public_query(query_id)})
                decision = self._decide({
                    "action": "hold", "verdict": "incident", "trigger": "operator_timeout",
                    "reason": f"query {query_id} expired unanswered: keeping the champion (safe default)",
                    "evidence": {"query_id": query_id}, "query_id": query_id,
                })
        return decision

    def answer_query(self, query_id: str, answer: str, operator: str = "operator") -> dict:
        """
        Apply an operator's answer to an open query. "new_normal" promotes the pending,
        already validated challenger; "incident" confirms the hold and pauses asking for
        query_cooldown events. Both are recorded with the query id and the operator.
        """
        if answer not in ("new_normal", "incident"):
            raise ValueError("answer must be 'new_normal' or 'incident'")
        q = self.queries.get(query_id)
        if q is None or q["status"] != "open":
            raise KeyError(f"no open query {query_id}")
        if self._pending is not None:
            raise RuntimeError("a lifecycle decision is in progress; retry in a moment")
        q.update(status="answered", answer=answer, operator=operator, answered_step=self.step)
        candidate = q.pop("_candidate")
        evidence = {**q["evidence"], "query_id": query_id, "operator": operator, "answer": answer}
        if answer == "new_normal":
            reason = f"operator {operator} confirmed a new normal (query {query_id})"
            apply(self.model, candidate["state"])
            self.shifts = {}
            self.ref_stats = candidate["ref_stats"]
            self.threshold, self.learn_gate = candidate["threshold"], candidate["gate"]
            version = self.registry.register(
                self._snapshot(), self.threshold, self.cfg.target_rate, step=self.step, reason=reason,
                tags={"kind": "challenger", "verdict": "concept_drift", "learn_gate": self.learn_gate,
                      "query_id": query_id, "operator": operator},
            )
            self.registry.set_production(version, step=self.step, transition="promote",
                                         reason=reason, evidence=evidence)
            if self.phase == "quarantine":   # the answer supersedes an observation in progress
                self.phase = "stable"
            self.monitor.reset()
            self._cooldown_until = self.step + self.cfg.cooldown
            action, verdict = "promote", "concept_drift"
        else:
            reason = f"operator {operator} confirmed an incident (query {query_id}): champion kept"
            self._ask_cooldown_until = self.step + self.cfg.query_cooldown
            action, verdict = "hold", "incident"
        self.publisher.publish_lifecycle({"event": "query_answered", **self.public_query(query_id)})
        return self._decide({"action": action, "verdict": verdict, "trigger": "operator",
                             "reason": reason, "evidence": evidence, "query_id": query_id})

    def request_validity_check(self, operator: str = "operator") -> bool:
        """Open a quarantine now, as the scheduled check would (UI 'check model' button)."""
        if self.cfg.policy != "cadal" or self.phase != "stable":
            return False
        self._open_quarantine("operator")
        return True

    def manual_set_version(self, version: int, transition: str, operator: str = "operator") -> dict:
        """
        Serve a registered version because an operator said so (UI promote / rollback). Recorded
        as an ordinary audited transition, with the version's alarm rate on recent traffic as
        evidence of what the operator chose.
        """
        if transition not in ("promote", "rollback"):
            raise ValueError("transition must be 'promote' or 'rollback'")
        if self._pending is not None:
            raise RuntimeError("a lifecycle decision is in progress; retry in a moment")
        target = self.registry.get(version)
        recent = list(self._recent_rows)[-200:]
        evidence = {"operator": operator, "target_version": version}
        if recent:
            evidence["target_recent_alarm_rate"] = round(self._alarm_rate_of(target, recent), 4)
        self._restore(target.state)
        self.threshold = target.threshold
        self.learn_gate = target.tags.get("learn_gate", target.threshold)
        reason = f"manual {transition} to v{version} by {operator}"
        self.registry.set_production(version, step=self.step, transition=transition,
                                     reason=reason, evidence=evidence)
        if self.phase == "quarantine":
            self.phase = "stable"
        self.monitor.reset()
        self._cooldown_until = self.step + self.cfg.cooldown
        return self._decide({"action": transition, "verdict": "operator", "trigger": "operator",
                             "reason": reason, "evidence": evidence})

    def _close_quarantine(self) -> Optional[dict]:
        ctx = self._quarantine_context()
        if not self.cfg.async_decisions:
            out = self._evaluate_quarantine(self.model, ctx)
            out["blocked_ms"] = out["eval_ms"]  # synchronous: scoring waited for the evaluation
            return self._apply_outcome(out)
        # Asynchronous: evaluate on a copy of the champion in the background, keep serving the
        # champion meanwhile, and swap in the outcome on the first event after it is ready.
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"cadal-{self.service_id}")
        # A look still running is about a shorter buffer than this decision: let it finish unused.
        self.phase = "deciding"
        self._pending_kind = "decision"
        self._pending = self._executor.submit(self._evaluate_quarantine, copy.deepcopy(self.model), ctx)
        return None

    def wait_for_decision(self, timeout: Optional[float] = None) -> Optional[dict]:
        """Block until a pending asynchronous decision or look is ready and apply it (tests, shutdown)."""
        if self._pending is None:
            return None
        return self._take_pending(self._pending.result(timeout=timeout))

    def _snapshot(self) -> HSTState:
        return capture(self.model, meta={
            "shifts": self.shifts,
            "ref_stats": {k: list(v) for k, v in self.ref_stats.items()} if self.ref_stats else None,
        })

    def _restore(self, state: HSTState) -> None:
        """Serve a registered version: model state plus its re-baselining state."""
        apply(self.model, state)
        self.shifts = dict(state.meta.get("shifts") or {})
        ref = state.meta.get("ref_stats")
        self.ref_stats = {k: tuple(v) for k, v in ref.items()} if ref else None

    def _alarm_rate_of(self, version, rows: list[dict], model=None) -> float:
        """Alarm rate a registered version would produce on `rows` (model restored afterwards)."""
        model = self.model if model is None else model
        current = capture(model)
        apply(model, version.state)
        shifts = version.state.meta.get("shifts") or {}
        rate = sum(_clamp(model.score_one(rebaselined(r, shifts))) >= version.threshold
                   for r in rows) / len(rows)
        apply(model, current)
        return rate

    def _decide(self, decision: dict) -> dict:
        decision = {"service_id": self.service_id, "step": self.step,
                    "version": self.registry.production_version, "threshold": self.threshold,
                    **decision}
        self.decisions.append(decision)
        self.publisher.publish_lifecycle({"event": "lifecycle_decision", **decision})
        return decision
