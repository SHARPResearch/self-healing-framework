import math
import random

import pytest

from src.change_events import ChangeEvent, ReplayChangeEventSource
from src.config import HSTConfig
from src.drift_attribution import AttributionConfig
from src.hst_model import build_model
from src.hst_state import capture
from src.lifecycle_manager import DynamicModelManager, LifecycleConfig
from src.publishers import RecordingPublisher

HST = HSTConfig(n_trees=15, height=6, window_size=50, seed=11)
FEATURES = ("a", "b", "c", "d")


def _normal(rng, shift=0.0):
    return {f: min(1.0, 0.3 + rng.gauss(0, 0.04) + (shift if f in ("a", "b") else 0.0)) for f in FEATURES}


def _cfg(policy="cadal", **kw):
    base = dict(
        policy=policy, calib_percentile=95.0, quarantine_with_change=200, quarantine_silent=400,
        change_horizon=200, cooldown=50, scheduled_every=10**9, scheduled_window=100,
        periodic_window=300, naive_stable_every=200,
    )
    base.update(kw)
    return LifecycleConfig(**base)


def _manager(cfg, events=(), publisher=None):
    mgr = DynamicModelManager(
        "svc", cfg, HST, change_source=ReplayChangeEventSource(events), publisher=publisher,
    )
    rng = random.Random(0)
    mgr.warm_up([_normal(rng) for _ in range(600)])
    return mgr


def _run(mgr, rows):
    return list(mgr.run(rows))


def _shifted_stream(n_before=300, n_after=900, seed=1, shift=0.35):
    rng = random.Random(seed)
    return [_normal(rng) for _ in range(n_before)] + [_normal(rng, shift) for _ in range(n_after)]


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        LifecycleConfig(policy="nope")


def test_warm_up_registers_production_v1_with_calibrated_threshold():
    mgr = _manager(_cfg())
    assert mgr.registry.production().version == 1
    assert 0.0 < mgr.threshold <= 1.0
    assert mgr.registry.production().threshold == mgr.threshold


def test_static_policy_never_changes_the_model():
    mgr = _manager(_cfg("static"))
    before = capture(mgr.model).masses
    _run(mgr, _shifted_stream())
    assert capture(mgr.model).masses == before
    assert mgr.decisions == []


def test_cadal_adapts_to_benign_shift_announced_by_a_deployment():
    pub = RecordingPublisher()
    mgr = _manager(_cfg(), events=[ChangeEvent("svc", "deployment", step=301)], publisher=pub)
    results = _run(mgr, _shifted_stream())

    promotions = [d for d in mgr.decisions if d["action"] == "promote"]
    assert promotions and promotions[0]["verdict"] == "concept_drift"
    assert promotions[0]["trigger"] == "change_event"
    assert "svc:deployment@301" in promotions[0]["reason"]
    assert mgr.registry.production().version > 1
    # After promotion the shifted regime is normal again: alarm rate back near target.
    tail = results[-300:]
    assert sum(r.alarm for r in tail) / len(tail) < 0.15
    assert any(p["event"] == "quarantine_opened" for p in pub.payloads)
    assert any(p["event"] == "lifecycle_decision" for p in pub.payloads)


def test_static_keeps_alarming_on_the_same_benign_shift():
    results = _run(_manager(_cfg("static")), _shifted_stream())
    tail = results[-300:]
    assert sum(r.alarm for r in tail) / len(tail) > 0.5


def test_cadal_needs_longer_persistence_without_a_change_event():
    with_event = _manager(_cfg(), events=[ChangeEvent("svc", "deployment", step=301)])
    _run(with_event, _shifted_stream())
    silent = _manager(_cfg(use_change_events=False))
    _run(silent, _shifted_stream())

    first = lambda m: next(d["step"] for d in m.decisions if d["action"] == "promote")
    assert first(with_event) < first(silent)


def test_deployment_without_behaviour_change_resumes_without_adapting():
    rng = random.Random(4)
    mgr = _manager(_cfg(), events=[ChangeEvent("svc", "deployment", step=100)])
    _run(mgr, [_normal(rng) for _ in range(600)])
    assert [d["verdict"] for d in mgr.decisions] == ["no_change"]
    assert mgr.registry.production().version == 1


def test_transient_burst_does_not_cause_adaptation():
    rng = random.Random(5)
    rows = [_normal(rng) for _ in range(300)]
    rows += [{f: rng.random() for f in FEATURES} for _ in range(60)]  # short incident
    rows += [_normal(rng) for _ in range(900)]
    mgr = _manager(_cfg())
    _run(mgr, rows)
    assert all(d["action"] != "promote" for d in mgr.decisions)
    assert mgr.registry.production().version == 1


def _escalating_incident(seed=6, n_before=300, n_incident=1200):
    """Flapping service whose oscillation keeps growing (a slowly escalating incident)."""
    rng = random.Random(seed)
    rows = [_normal(rng) for _ in range(n_before)]
    for i in range(n_incident):
        amp = 0.05 + 0.6 * i / n_incident
        row = _normal(rng)
        row["a"] = min(1.0, max(0.0, 0.3 + amp * math.sin(i / 5)))
        row["b"] = min(1.0, max(0.0, 0.3 + amp * math.cos(i / 3)))
        rows.append(row)
    return rows


def _runaway_incident(seed=7, n_before=300, n_incident=1500):
    """Non-stationary incident: a metric that keeps climbing (no plateau to call a new normal)."""
    rng = random.Random(seed)
    rows = [_normal(rng) for _ in range(n_before)]
    for i in range(n_incident):
        row = _normal(rng)
        row["a"] = 0.3 + 0.002 * i + rng.gauss(0, 0.04)
        rows.append(row)
    return rows


def test_runaway_incident_is_never_learned():
    # The challenger itself cannot see the runaway (values beyond its fitted range land in an
    # edge cell it already populated); the support check and frozen serving keep it out of the
    # model, so the champion stays v1 and keeps alarming.
    mgr = _manager(_cfg())
    results = _run(mgr, _runaway_incident())
    assert mgr.decisions, "the incident should trigger a quarantine"
    assert all(d["action"] != "promote" for d in mgr.decisions)
    assert mgr.registry.production().version == 1
    assert any(d["evidence"]["tail_out_of_support_rate"] == 1.0 for d in mgr.decisions)
    assert sum(r.alarm for r in results[-300:]) / 300 > 0.1


def test_strict_learn_gate_resists_absorbing_an_escalating_incident():
    # Gating learning on the alarm threshold itself lets the incident creep into "normal";
    # gating on the 75th calibration percentile keeps the model sensitive for longer.
    loose = _manager(_cfg(learn_gate_percentile=95.0))
    strict = _manager(_cfg(learn_gate_percentile=75.0))
    rate = lambda res: sum(r.alarm for r in res[300:570]) / 270
    assert rate(_run(strict, _escalating_incident())) > 2 * rate(_run(loose, _escalating_incident()))


def _spy_on_close(mgr):
    """Record the champion (state, threshold, gate) at the moment each quarantine closes."""
    seen = []
    original = mgr._close_quarantine

    def spy():
        seen.append((capture(mgr.model).masses, mgr.threshold, mgr.learn_gate))
        return original()

    mgr._close_quarantine = spy
    return seen


def _assert_restored_on(action, rows, events=(), cfg=None):
    mgr = DynamicModelManager("svc", cfg or _cfg(), HST, change_source=ReplayChangeEventSource(events))
    rng = random.Random(0)
    mgr.warm_up([_normal(rng) for _ in range(600)])
    seen = _spy_on_close(mgr)
    for x in rows:
        res = mgr.process(x)
        if res.lifecycle:
            assert res.lifecycle["action"] == action, res.lifecycle
            assert (capture(mgr.model).masses, mgr.threshold, mgr.learn_gate) == seen[-1]
            return
    pytest.fail(f"expected a {action} decision")


def test_hold_restores_the_champion_exactly():
    # With nothing allowed to count as learnable, a persistent shift must be held as an incident.
    never_learnable = AttributionConfig(learnable_factor=0.0, z=0.0)
    _assert_restored_on("hold", _shifted_stream(), events=[ChangeEvent("svc", "deployment", step=301)],
                        cfg=_cfg(attribution=never_learnable))


def test_resume_restores_the_champion_exactly():
    rng = random.Random(4)
    _assert_restored_on("resume", [_normal(rng) for _ in range(600)],
                        events=[ChangeEvent("svc", "deployment", step=100)])


def test_naive_rollback_rolls_back_on_every_drift_including_benign_ones():
    mgr = _manager(_cfg("naive_rollback"))
    _run(mgr, _shifted_stream())
    assert any(d["action"] == "rollback" for d in mgr.decisions)
    assert all(d["verdict"] == "unattributed" for d in mgr.decisions)


def test_periodic_policy_retrains_on_schedule():
    mgr = _manager(_cfg("periodic", scheduled_every=400))
    _run(mgr, _shifted_stream(n_before=300, n_after=900))
    assert [d["step"] for d in mgr.decisions] == [400, 800, 1200]
    assert mgr.registry.production().version == 4


def test_every_transition_is_in_the_registry_audit_log():
    mgr = _manager(_cfg(), events=[ChangeEvent("svc", "deployment", step=301)])
    _run(mgr, _shifted_stream())
    kinds = [t.transition for t in mgr.registry.transitions]
    assert kinds[:2] == ["register", "promote"]
    promote = [t for t in mgr.registry.transitions if t.transition == "promote"][-1]
    assert promote.evidence["change_event_id"] == "svc:deployment@301"


def test_start_from_shared_warm_state_matches_a_full_warm_up():
    full = _manager(_cfg("static"))
    shared_model = build_model(HST)
    rng = random.Random(0)
    rows = [_normal(rng) for _ in range(600)]
    split = int(len(rows) * 0.8)
    for r in rows[:split]:
        shared_model.learn_one(r)
    calib = [min(max(shared_model.score_one(r), 0.0), 1.0) for r in rows[split:]]
    for r in rows[split:]:
        shared_model.learn_one(r)
    warm = capture(shared_model)
    for r in _shifted_stream()[:200]:
        shared_model.learn_one(r)  # dirty the shared model, start_from must undo this

    mgr = DynamicModelManager("svc", _cfg("static"), HST, model=shared_model)
    mgr.start_from(warm, calib, rows[-300:])
    assert mgr.threshold == full.threshold and mgr.learn_gate == full.learn_gate
    assert capture(mgr.model).masses == capture(full.model).masses


def test_rollback_is_refused_when_the_target_flags_the_new_normal():
    # Promote to the post-deployment regime, then force a "decay" verdict on that same regime:
    # restoring the pre-deployment v1 would alarm on nearly everything, so the manager keeps
    # the champion instead of ping-ponging back (the failure of unconditional rollback).
    cfg = _cfg(attribution=AttributionConfig(decay_factor=10.0))
    mgr = _manager(cfg, events=[ChangeEvent("svc", "deployment", step=301)])
    rng = random.Random(1)
    _run(mgr, [_normal(rng) for _ in range(300)] + [_normal(rng, 0.35) for _ in range(500)])
    promoted = mgr.registry.production().version
    assert promoted > 1

    mgr._open_quarantine("drift_down")
    _run(mgr, [_normal(rng, 0.35) for _ in range(mgr._q_target_len)])
    last = mgr.decisions[-1]
    assert last["verdict"] == "no_change" and last["action"] == "resume"
    assert last["evidence"]["rollback_target_version"] == 1
    assert last["evidence"]["rollback_target_tail_alarm_rate"] >= 0.5
    assert mgr.registry.production().version == promoted


def test_out_of_support_rate_flags_values_beyond_the_fitted_range():
    from src.lifecycle_manager import out_of_support_rate
    fit = [{"a": 0.1 * i, "b": 0.5} for i in range(11)]  # a in [0, 1], b flat
    assert out_of_support_rate(fit, [{"a": 0.5, "b": 0.5}, {"a": 1.05, "b": 0.5}]) == 0.0
    # Worst single feature counts: a leaves its range in 1 of 2 rows, b in 1 of 2 rows.
    assert out_of_support_rate(fit, [{"a": 1.2, "b": 0.5}, {"a": 0.5, "b": 0.6}]) == 0.5
    assert out_of_support_rate(fit, [{"a": 1.2, "b": 0.5}, {"a": 1.3, "b": 0.5}]) == 1.0


def test_verified_rollback_restores_the_previous_production_version(monkeypatch):
    import src.lifecycle_manager as lm
    from src.drift_attribution import Action, Attribution, Verdict

    mgr = _manager(_cfg(), events=[ChangeEvent("svc", "deployment", step=301)])
    rng = random.Random(1)
    _run(mgr, [_normal(rng) for _ in range(300)] + [_normal(rng, 0.35) for _ in range(500)])
    assert mgr.registry.production().version == 2
    v1 = mgr.registry.get(1)

    # The service itself is rolled back (old behaviour returns) and the next quarantine is
    # attributed to decay; v1 fits the returned behaviour, so the rollback is verified and runs.
    monkeypatch.setattr(lm, "attribute", lambda ev, cfg: Attribution(
        Verdict.MODEL_DECAY, Action.ROLLBACK, "forced for test", {}))
    mgr._open_quarantine("drift_down")
    seen = []
    for x in [_normal(rng) for _ in range(mgr._q_target_len)]:
        res = mgr.process(x)
        if res.lifecycle:
            seen.append(res.lifecycle)
    assert seen and seen[0]["action"] == "rollback"
    assert seen[0]["evidence"]["rollback_target_version"] == 1
    assert mgr.registry.production().version == 1
    assert capture(mgr.model).masses == v1.state.masses
    assert mgr.threshold == v1.threshold and mgr.learn_gate == v1.tags["learn_gate"]
    assert mgr.registry.transitions[-1].transition == "rollback"
