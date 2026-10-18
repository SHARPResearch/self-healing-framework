"""
drift_attribution.py — Component 2: decide *what kind* of shift was detected before acting on it.

The problem this solves (the "drift response dilemma"): in unsupervised streaming anomaly
detection, a detected shift in the anomaly score stream has at least three causes that need
opposite responses:

  INCIDENT       the service is actually failing. Correct response: keep the current model,
                 keep alerting, and do NOT learn from these events (learning them teaches the
                 model that the failure is normal, i.e. self-poisoning).
  CONCEPT_DRIFT  the service legitimately changed (new deployment, new traffic mix) and the
                 old "normal" no longer applies. Correct response: adopt a model and threshold
                 fitted to the new regime, otherwise every event alarms forever.
  MODEL_DECAY    the model has become insensitive (scores collapsed, e.g. after absorbing a
                 long anomaly). Correct response: roll back to the last good version.

A policy that always rolls back (the original Component 2 design) is right only for the third
case and actively harmful for the second: restoring the pre-deployment model brings the
pre-deployment notion of normal back. A policy that always keeps learning is wrong for the
first. Attribution uses label-free evidence gathered during a short quarantine (learning frozen,
alerting continues) to pick the response:

  persistence    is the champion still alarming at the end of the quarantine? Incidents end,
                 new normals do not.
  learnability   a challenger fitted on the first part of the quarantine buffer and calibrated
                 on the middle part: does it find the tail of the buffer normal? A stable new
                 regime is self-consistent; an incident in progress usually is not.
  support        does the tail stay inside the value range the challenger was fitted on? A
                 new steady regime does; a trend keeps leaving it. Needed because tree models
                 (HST included) put every value beyond the fitted range into the same edge cell,
                 so a runaway metric looks "learnable" to the challenger itself.
  repair         two candidate repairs are tested the same way: *re-baselining* (keep the
                 champion and everything it learned, shift the inputs of the metrics whose
                 level moved back onto its baseline) and *retraining* (a challenger fitted only on
                 the new regime). Re-baselining is preferred when it passes: a challenger fitted
                 on a day of data forgets the weeks of normal variation the champion knew.
  change prior   did an exogenous change (deployment, config) precede the shift? If so, less
                 persistence is required before accepting it as a new normal.
  direction      scores shifting down instead of up points at decay, not drift.

Pure functions only: no model state, no I/O, so every rule is unit tested directly.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Verdict(str, Enum):
    INCIDENT = "incident"
    CONCEPT_DRIFT = "concept_drift"
    MODEL_DECAY = "model_decay"
    NO_CHANGE = "no_change"


class Action(str, Enum):
    HOLD = "hold"            # keep champion, keep learning gated (incident)
    PROMOTE = "promote"      # challenger becomes champion (concept drift)
    ROLLBACK = "rollback"    # restore last production version (decay)
    RESUME = "resume"        # nothing changed, resume normal gated learning


VERDICT_ACTION = {
    Verdict.INCIDENT: Action.HOLD,
    Verdict.CONCEPT_DRIFT: Action.PROMOTE,
    Verdict.MODEL_DECAY: Action.ROLLBACK,
    Verdict.NO_CHANGE: Action.RESUME,
}


@dataclass(frozen=True)
class AttributionConfig:
    """
    Decision thresholds, all expressed as multiples of the target alarm rate r0 (the rate the
    per-entity calibrated threshold is designed to produce on normal data, e.g. 3% at the 97th
    percentile), so the same config transfers across entities with different score scales.
    """
    stale_factor_with_change: float = 2.0   # champion tail alarm rate needed when a change preceded
    stale_factor_silent: float = 4.0        # ... and when nothing explains the shift
    learnable_factor: float = 2.0           # challenger tail alarm rate allowed for "self-consistent"
    decay_factor: float = 0.2               # champion alarm rate below this * r0 means insensitive
    z: float = 2.33                         # one-sided 99% binomial slack on the learnable line
    # A rollback target must still discriminate on recent data: a version that flags at least
    # this share of recent events (e.g. the pre-deployment model on a new normal) is not restored.
    rollback_max_alarm_rate: float = 0.5
    moving_feature_rate: float = 0.5        # a feature out of fitted support this often is trending
    # Only an exogenous change licenses *replacing* the model. Without one, a persistent shift
    # that only a freshly retrained challenger explains is held as a probable incident: on SMD a
    # day-long incident is self-consistent enough to pass the learnability test, and retraining
    # on it silenced the detector for the rest of the incident (machine-1-1, recall 0.87 -> 0.08).
    # Re-baselining stays allowed without a change, since it keeps everything the champion knew.
    retrain_requires_change: bool = True


@dataclass(frozen=True)
class QuarantineEvidence:
    trigger: str                              # "drift_up" | "drift_down" | "change_event" | "scheduled"
    target_rate: float                        # r0
    champion_alarm_rate: float                # over the whole quarantine
    champion_tail_alarm_rate: float           # over the tail (last part) of the quarantine
    challenger_tail_alarm_rate: Optional[float]  # None if no challenger could be fitted
    change_event_id: Optional[str] = None     # most recent change event inside the horizon
    n_tail: Optional[int] = None              # tail size, for the sampling-noise slack
    tail_out_of_support_rate: Optional[float] = None  # max per-feature share of tail outside the fit range
    # Per-entity null: what the same stationarity test gives on windows of the entity's own
    # normal training data (see lifecycle_manager.attribution_null). Raise the lines to these
    # floors so natural non-stationarity (daily cycles, spiky features) is not read as "moving".
    learnable_floor: Optional[float] = None
    moving_floor: Optional[float] = None
    # Tail alarm rate of the champion after re-baselining the shifted metrics (None: no metric
    # moved enough to re-baseline, or re-baselining not available).
    rebaseline_tail_alarm_rate: Optional[float] = None


@dataclass(frozen=True)
class Attribution:
    verdict: Verdict
    action: Action
    reason: str
    evidence: dict = field(default_factory=dict)


def attribute(ev: QuarantineEvidence, cfg: AttributionConfig = AttributionConfig()) -> Attribution:
    """Map quarantine evidence to a verdict and lifecycle action, with a readable reason."""
    r0 = ev.target_rate
    has_change = ev.change_event_id is not None
    stale_factor = cfg.stale_factor_with_change if has_change else cfg.stale_factor_silent
    stale_line = stale_factor * r0
    # A challenger calibrated to r0 on a few hundred events will not hit r0 exactly on the tail;
    # allow for binomial sampling noise so a learnable regime is not rejected on noise alone.
    slack = cfg.z * math.sqrt(r0 * (1 - r0) / ev.n_tail) if ev.n_tail else 0.0
    learnable_line = max(cfg.learnable_factor * r0 + slack, ev.learnable_floor or 0.0)
    # Re-baselining keeps the champion and its calibrated threshold, so it is held to the target
    # rate plus sampling slack only. The per-entity floor measures how noisy a *freshly retrained*
    # challenger is on normal windows and does not apply to it: with a PCA detector that floor
    # reached ~0.6 and let re-baselining through at a 55% tail alarm rate (machine-1-6).
    rebaseline_line = cfg.learnable_factor * r0 + slack
    moving_line = max(cfg.moving_feature_rate, ev.moving_floor or 0.0)

    evidence = {
        "trigger": ev.trigger,
        "target_rate": r0,
        "champion_alarm_rate": round(ev.champion_alarm_rate, 4),
        "champion_tail_alarm_rate": round(ev.champion_tail_alarm_rate, 4),
        "challenger_tail_alarm_rate": (
            None if ev.challenger_tail_alarm_rate is None else round(ev.challenger_tail_alarm_rate, 4)
        ),
        "change_event_id": ev.change_event_id,
        "n_tail": ev.n_tail,
        "rebaseline_tail_alarm_rate": (
            None if ev.rebaseline_tail_alarm_rate is None else round(ev.rebaseline_tail_alarm_rate, 4)
        ),
        "tail_out_of_support_rate": (
            None if ev.tail_out_of_support_rate is None else round(ev.tail_out_of_support_rate, 4)
        ),
        "moving_line": round(moving_line, 4),
        "stale_line": round(stale_line, 4),
        "learnable_line": round(learnable_line, 4),
        "rebaseline_line": round(rebaseline_line, 4),
    }

    def done(verdict: Verdict, reason: str) -> Attribution:
        return Attribution(verdict, VERDICT_ACTION[verdict], reason, evidence)

    if ev.trigger == "drift_down" and ev.champion_alarm_rate < cfg.decay_factor * r0:
        return done(
            Verdict.MODEL_DECAY,
            f"scores shifted down and champion alarm rate {ev.champion_alarm_rate:.4f} is below "
            f"{cfg.decay_factor} x target {r0:.4f}: model has become insensitive",
        )

    if ev.champion_tail_alarm_rate < stale_line:
        return done(
            Verdict.NO_CHANGE,
            f"champion tail alarm rate {ev.champion_tail_alarm_rate:.4f} is under the stale line "
            f"{stale_line:.4f}: shift did not persist, champion still fits",
        )

    if ev.challenger_tail_alarm_rate is None:
        return done(Verdict.INCIDENT, "champion is alarming persistently and no challenger could be fitted")

    if ev.tail_out_of_support_rate is not None and ev.tail_out_of_support_rate > moving_line:
        return done(
            Verdict.INCIDENT,
            f"champion alarming persistently and a feature is outside the range the challenger was "
            f"fitted on for {ev.tail_out_of_support_rate:.4f} of the tail (> {moving_line:.4f}): "
            f"the behaviour is still moving, not a new steady state",
        )

    why = f"after change {ev.change_event_id}" if has_change else "with no explaining change event"
    stale = (f"champion stale (tail alarm rate {ev.champion_tail_alarm_rate:.4f} >= {stale_line:.4f})")
    if ev.rebaseline_tail_alarm_rate is not None and ev.rebaseline_tail_alarm_rate <= rebaseline_line:
        evidence["repair"] = "rebaseline"
        return done(
            Verdict.CONCEPT_DRIFT,
            f"{stale} and re-baselining the shifted metrics restores it (tail rate "
            f"{ev.rebaseline_tail_alarm_rate:.4f} <= {rebaseline_line:.4f}) {why}",
        )
    if ev.challenger_tail_alarm_rate <= learnable_line and cfg.retrain_requires_change and not has_change:
        return done(
            Verdict.INCIDENT,
            f"{stale}; only a retrained challenger explains the new regime (tail rate "
            f"{ev.challenger_tail_alarm_rate:.4f}) and no change event explains it, so it is held as a "
            f"probable incident: replacing the model needs a deployment or config change",
        )
    if ev.challenger_tail_alarm_rate <= learnable_line:
        evidence["repair"] = "retrain"
        return done(
            Verdict.CONCEPT_DRIFT,
            f"{stale} and the new regime is learnable (challenger tail rate "
            f"{ev.challenger_tail_alarm_rate:.4f} <= {learnable_line:.4f}) {why}",
        )

    return done(
        Verdict.INCIDENT,
        f"champion alarming persistently but the new regime is not self-consistent (challenger "
        f"tail rate {ev.challenger_tail_alarm_rate:.4f} > {learnable_line:.4f}): treating as incident",
    )
