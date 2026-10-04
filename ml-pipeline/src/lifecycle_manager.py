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

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Optional

import numpy as np

from src.change_events import ChangeEvent, ChangeEventSource, NullChangeEventSource
from src.config import HST_CFG, HSTConfig
from src.drift_attribution import (
    Action, Attribution, AttributionConfig, QuarantineEvidence, Verdict, attribute,
)
from src.drift_detectors import ScoreDriftMonitor
from src.hst_model import build_model, classify_severity
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
    # cadal learns only events scoring below this percentile of calibration scores. 0 (default)
    # disables continuous learning: the served model changes only through versioned, attributed,
    # validated transitions. On SMD every continuously learning variant lost recall, because
    # HST's sliding reference window absorbs long anomaly segments. A positive value (e.g. 75)
    # gives the gated-learning variant; gating on the alarm threshold itself would let a slowly
    # escalating incident creep into "normal" one just-below-threshold event at a time.
    learn_gate_percentile: float = 0.0
    detector: str = "adwin"
    adwin_delta: float = 0.002
    # Quarantine lengths (events). SMD is sampled once a minute, so 720 = 12 h, 1440 = 1 day.
    # Each must leave the challenger's fit slice >= HST window_size or it cannot score at all.
    quarantine_with_change: int = 720
    quarantine_silent: int = 1440
    change_horizon: int = 720               # a change explains drift detected within this many steps
    fit_frac: float = 0.5                   # quarantine buffer split: fit / calib / tail
    calib_frac: float = 0.3
    cooldown: int = 250                     # ignore drift signals right after a decision
    scheduled_every: int = 2880             # time trigger + checkpoint cadence (2 days)
    scheduled_window: int = 720             # alarm-rate window for the scheduled validity check
    periodic_window: int = 1440             # training window for the periodic policy
    naive_stable_every: int = 1000          # naive_rollback stable-snapshot cadence (guide Part 5)
    attribution: AttributionConfig = field(default_factory=AttributionConfig)
    null_windows: int = 8                   # training windows per quarantine length (0 disables)
    null_quantile: float = 0.9              # normal windows pass the stationarity test this often

    def __post_init__(self):
        if self.policy not in POLICIES:
            raise ValueError(f"Unknown policy {self.policy!r}, expected one of {POLICIES}")

    @property
    def learns_while_serving(self) -> bool:
        """Whether the served model keeps learning between versions (decides how to calibrate)."""
        if self.policy == "cadal":
            return self.learn_gate_percentile > 0
        return self.policy not in ("static", "periodic")

    @property
    def target_rate(self) -> float:
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

        self.decisions: list[dict] = []
        self.attribution_null: dict[int, dict[str, float]] = {}
        self.transition_ms: list[float] = []

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
        frozen = [_clamp(self.model.score_one(r)) for r in rows[split:]]
        prequential = self._prequential(rows[split:])
        calib_scores = prequential if self.cfg.learns_while_serving else frozen
        null = attribution_null(self, rows) if self.cfg.policy == "cadal" else {}
        self.start_from(None, calib_scores, rows[-self.cfg.periodic_window:], null)
        duration = time.perf_counter() - start
        return {"events": len(rows), "duration_s": round(duration, 2), "threshold": self.threshold}

    def start_from(self, state: Optional[HSTState], calib_scores: list[float],
                   recent_rows: list[dict], null: Optional[dict] = None) -> None:
        """
        Begin serving from an already warmed-up state (None = the model as it is now).

        Lets many policies or replicas share one expensive warm-up: apply the warm state to a
        structurally identical model, calibrate from the same held-out scores, register v1.
        """
        if state is not None:
            apply(self.model, state)
        self.attribution_null = dict(null or {})
        self.threshold, self.learn_gate = self._calibrate(calib_scores)
        self._recent_rows.extend(recent_rows)
        version = self.registry.register(
            capture(self.model), self.threshold, self.cfg.target_rate,
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

        for evt in self.changes.poll(self.step):
            decision = self._on_change_event(evt) or decision

        score = _clamp(self.model.score_one(x))
        alarm = score >= self.threshold
        self._recent_alarms.append(alarm)
        self._recent_rows.append(x)
        self._recent_scores.append(score)

        policy = self.cfg.policy
        if policy == "online":
            self.model.learn_one(x)
        elif policy == "gated":
            if not alarm:
                self.model.learn_one(x)
        elif policy == "naive_rollback":
            decision = self._naive_rollback_step(x, score) or decision
        elif policy == "periodic":
            if self.step % self.cfg.scheduled_every == 0:
                decision = self._periodic_retrain()
        elif policy == "cadal":
            decision = self._cadal_step(x, score, alarm) or decision

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
        apply(self.model, target.state)
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
        threshold = float(np.percentile(calib_scores, self.cfg.calib_percentile))
        gate_pct = self.cfg.learn_gate_percentile
        gate = float(np.percentile(calib_scores, gate_pct)) if gate_pct > 0 else -1.0
        return threshold, min(gate, threshold)

    def _prequential(self, rows: list[dict]) -> list[float]:
        """Score each row, then learn it: the way a serving model sees the stream."""
        scores = []
        for r in rows:
            scores.append(_clamp(self.model.score_one(r)))
            self.model.learn_one(r)
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

    def _fit_challenger(self, rows: list[dict], calib_rows: list[dict]) -> tuple[float, float]:
        """
        Reset the model in place, learn `rows`, return (threshold, gate) calibrated on frozen
        scores of `calib_rows`. The caller decides whether the model then learns `calib_rows`.
        """
        reset(self.model, keep_scaler=True)
        for r in rows:
            self.model.learn_one(r)
        return self._calibrate([_clamp(self.model.score_one(r)) for r in calib_rows])

    def _checkpoint(self, reason: str) -> None:
        t = time.perf_counter()
        self.registry.checkpoint(capture(self.model), self.threshold, self.cfg.target_rate,
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
        version = self.registry.register(capture(self.model), self.threshold, self.cfg.target_rate,
                                         step=self.step, reason="scheduled retrain on recent window")
        self.registry.set_production(version, step=self.step, transition="promote",
                                     reason="scheduled retrain (unconditional)")
        self.transition_ms.append((time.perf_counter() - t) * 1000)
        return self._decide({"action": "promote", "verdict": "scheduled", "trigger": "scheduled"})

    def _change_in_horizon(self) -> Optional[str]:
        if not self.cfg.use_change_events or self._last_change is None:
            return None
        if self.step - self._last_change_step <= self.cfg.change_horizon:
            return self._last_change.event_id
        return None

    def _on_change_event(self, evt: ChangeEvent) -> Optional[dict]:
        if self.cfg.policy != "cadal" or not self.cfg.use_change_events:
            return None
        self._last_change, self._last_change_step = evt, self.step
        self.publisher.publish_lifecycle({"service_id": self.service_id, "event": "change_observed",
                                          "change_event_id": evt.event_id, "step": self.step})
        # Evidence about the post-change regime has to come from after the change, so a change
        # during an open quarantine restarts it rather than reusing the pre-change buffer.
        self._open_quarantine("change_event")
        return None

    def _open_quarantine(self, trigger: str) -> None:
        self.phase = "quarantine"
        self._q_trigger = trigger
        self._q_rows, self._q_alarms = [], []
        explained = trigger == "change_event" or self._change_in_horizon() is not None
        self._q_target_len = self.cfg.quarantine_with_change if explained else self.cfg.quarantine_silent
        self.publisher.publish_lifecycle({"service_id": self.service_id, "event": "quarantine_opened",
                                          "trigger": trigger, "step": self.step,
                                          "length": self._q_target_len})

    def _cadal_step(self, x: dict, score: float, alarm: bool) -> Optional[dict]:
        if score < self.learn_gate:
            self.model.learn_one(x)                 # gated learning: only clearly typical events teach

        if self.phase == "quarantine":
            self._q_rows.append(x)
            self._q_alarms.append(alarm)
            self.monitor.update(score, self.step)
            if len(self._q_rows) >= self._q_target_len:
                return self._close_quarantine()
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

    def _close_quarantine(self) -> dict:
        t = time.perf_counter()
        rows, alarms = self._q_rows, self._q_alarms
        n = len(rows)
        n_fit = int(n * self.cfg.fit_frac)
        n_calib = int(n * self.cfg.calib_frac)
        tail = slice(n_fit + n_calib, n)

        champion_state = capture(self.model)
        champion_threshold, champion_gate = self.threshold, self.learn_gate
        challenger_threshold, challenger_gate = self._fit_challenger(rows[:n_fit], rows[n_fit:n_fit + n_calib])
        # Learnability is a stationarity test, so it is measured frozen: fitted on the start of
        # the buffer, calibrated on the middle, does the model still find the tail normal? A new
        # steady regime passes; a trend or an escalating incident drifts away from the fit.
        tail_rows = rows[tail]
        challenger_tail = (
            sum(_clamp(self.model.score_one(r)) >= challenger_threshold for r in tail_rows) / len(tail_rows)
        )
        tail_alarms = alarms[tail]
        evidence = QuarantineEvidence(
            trigger=self._q_trigger,
            target_rate=self.cfg.target_rate,
            champion_alarm_rate=sum(alarms) / n,
            champion_tail_alarm_rate=sum(tail_alarms) / len(tail_alarms),
            challenger_tail_alarm_rate=challenger_tail,
            change_event_id=self._change_in_horizon(),
            n_tail=len(tail_rows),
            tail_out_of_support_rate=out_of_support_rate(rows[:n_fit], tail_rows),
            learnable_floor=self.attribution_null.get(n, {}).get("learnable"),
            moving_floor=self.attribution_null.get(n, {}).get("moving"),
        )
        result: Attribution = attribute(evidence, self.cfg.attribution)

        rollback_target = None
        if result.action is Action.ROLLBACK:
            rollback_target = self.registry.previous_production() or self.registry.production()
            target_rate = self._alarm_rate_of(rollback_target, rows[tail])
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

        if result.action is Action.PROMOTE:
            if self.cfg.learns_while_serving:
                # A learning model is served with a threshold calibrated the way it will run
                # (score each remaining buffered event, then learn it), not on the frozen
                # stationarity test.
                challenger_threshold, challenger_gate = self._calibrate(self._prequential(rows[n_fit:]))
            # A frozen-serving promotion serves exactly what was validated: the challenger
            # fitted on the fit slice with the threshold from frozen scores of the calib slice.
            self.threshold, self.learn_gate = challenger_threshold, challenger_gate
            version = self.registry.register(
                capture(self.model), self.threshold, self.cfg.target_rate, step=self.step,
                reason=result.reason, tags={"kind": "challenger", "verdict": result.verdict.value,
                                            "learn_gate": self.learn_gate},
            )
            self.registry.set_production(version, step=self.step, transition="promote",
                                         reason=result.reason, evidence=result.evidence)
        elif result.action is Action.ROLLBACK:
            target = rollback_target
            apply(self.model, target.state)
            self.threshold = target.threshold
            self.learn_gate = target.tags.get("learn_gate", target.threshold)
            self.registry.set_production(target.version, step=self.step, transition="rollback",
                                         reason=result.reason, evidence=result.evidence)
        else:  # HOLD or RESUME: the champion stays, exactly as it was
            apply(self.model, champion_state)
            self.threshold, self.learn_gate = champion_threshold, champion_gate

        self.monitor.reset()
        self.phase = "stable"
        self._cooldown_until = self.step + self.cfg.cooldown
        self.transition_ms.append((time.perf_counter() - t) * 1000)
        return self._decide({"action": result.action.value, "verdict": result.verdict.value,
                             "trigger": self._q_trigger, "reason": result.reason,
                             "evidence": result.evidence})

    def _alarm_rate_of(self, version, rows: list[dict]) -> float:
        """Alarm rate a registered version would produce on `rows` (model restored afterwards)."""
        current = capture(self.model)
        apply(self.model, version.state)
        rate = sum(_clamp(self.model.score_one(r)) >= version.threshold for r in rows) / len(rows)
        apply(self.model, current)
        return rate

    def _decide(self, decision: dict) -> dict:
        decision = {"service_id": self.service_id, "step": self.step,
                    "version": self.registry.production_version, "threshold": self.threshold,
                    **decision}
        self.decisions.append(decision)
        self.publisher.publish_lifecycle({"event": "lifecycle_decision", **decision})
        return decision
