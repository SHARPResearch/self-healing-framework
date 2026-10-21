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
        periodic_window=300, naive_stable_every=200, null_windows=3,
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
                        cfg=_cfg(attribution=never_learnable, null_windows=0))


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


def test_attribution_null_is_computed_from_training_windows_and_restores_the_model():
    from src.lifecycle_manager import attribution_null
    mgr = _manager(_cfg(quarantine_with_change=200, quarantine_silent=250))
    before = capture(mgr.model).masses
    rng = random.Random(3)
    null = attribution_null(mgr, [_normal(rng) for _ in range(600)])
    assert set(null) == {200, 250}
    assert all(0.0 <= v["learnable"] <= 1.0 and 0.0 <= v["moving"] <= 1.0 for v in null.values())
    assert capture(mgr.model).masses == before
    assert mgr.attribution_null, "warm_up computes the null for cadal"


def test_the_change_that_opened_a_long_quarantine_still_explains_it_at_close():
    # Quarantine (400) longer than the change horizon (100): the deployment that opened it must
    # still count as the explanation when it closes, so the lower stale line applies.
    cfg = _cfg(quarantine_with_change=400, quarantine_silent=400, change_horizon=100)
    mgr = _manager(cfg, events=[ChangeEvent("svc", "deployment", step=301)])
    _run(mgr, _shifted_stream())
    first = mgr.decisions[0]
    assert first["trigger"] == "change_event"
    assert first["evidence"]["change_event_id"] == "svc:deployment@301"
    assert first["evidence"]["stale_line"] == round(2.0 * cfg.target_rate, 4)


def test_for_sampling_rescales_every_length_to_the_same_wall_clock_time():
    from src.lifecycle_manager import hst_window_for_sampling
    smd = LifecycleConfig()
    nab = smd.for_sampling(288)  # five-minute samples
    assert nab.quarantine_silent == 288 and nab.scheduled_every == 576
    assert nab.periodic_window == 288 and nab.cooldown == 50
    assert smd.for_sampling(1440) == smd
    window = hst_window_for_sampling(288)
    assert window == 50 and int(nab.quarantine_silent * nab.fit_frac) >= window


@pytest.mark.parametrize("combine", ["mean", "max"])
def test_cadal_runs_end_to_end_on_the_lazy_ensemble_detector(combine):
    from dataclasses import replace as dc_replace
    hst = dc_replace(HST, lazy=True, range_margin=0.25, ensemble=combine)
    mgr = DynamicModelManager("svc", _cfg(), hst,
                              change_source=ReplayChangeEventSource([ChangeEvent("svc", "deployment", step=301)]))
    rng = random.Random(0)
    mgr.warm_up([_normal(rng) for _ in range(600)])
    assert mgr.model.dev is not None  # calibrated at warm-up
    results = _run(mgr, _shifted_stream())
    assert any(d["action"] == "promote" for d in mgr.decisions)
    assert sum(r.alarm for r in results[-300:]) / 300 < 0.2
    # The promoted version carries the ensemble state.
    assert mgr.registry.production().state.extra is not None


def test_level_shift_is_repaired_by_rebaselining_and_keeps_the_champion():
    mgr = _manager(_cfg(), events=[ChangeEvent("svc", "deployment", step=301)])
    v1_masses = mgr.registry.get(1).state.masses
    results = _run(mgr, _shifted_stream())
    promote = next(d for d in mgr.decisions if d["action"] == "promote")
    assert promote["evidence"]["repair"] == "rebaseline"
    assert set(promote["evidence"]["rebaselined"]) == {"a", "b"}
    assert all(0.25 < s < 0.45 for s in promote["evidence"]["rebaselined"].values())
    # Same model as warm-up, only the inputs are shifted.
    assert capture(mgr.model).masses == v1_masses
    assert sum(r.alarm for r in results[-300:]) / 300 < 0.15


def test_rebaselining_can_be_disabled_to_retrain_instead():
    mgr = _manager(_cfg(rebaseline=False), events=[ChangeEvent("svc", "deployment", step=301)])
    _run(mgr, _shifted_stream())
    promote = next(d for d in mgr.decisions if d["action"] == "promote")
    assert promote["evidence"]["repair"] == "retrain"
    assert mgr.shifts == {}


def test_rollback_restores_the_target_versions_shifts():
    from src.lifecycle_manager import robust_stats
    mgr = _manager(_cfg(), events=[ChangeEvent("svc", "deployment", step=301)])
    _run(mgr, _shifted_stream())
    assert mgr.shifts
    v1 = mgr.registry.get(1)
    mgr._restore(v1.state)
    assert mgr.shifts == {}
    assert mgr.ref_stats is not None and set(mgr.ref_stats) == set(FEATURES)
    assert robust_stats([_normal(random.Random(0))] * 3)["a"][1] == 1e-6  # flat floor


LAZY_HST = HSTConfig(n_trees=15, height=6, window_size=50, seed=11, lazy=True, range_margin=0.25)


def _lazy_manager(**cfg_kw):
    mgr = DynamicModelManager("svc", _cfg(**cfg_kw), LAZY_HST,
                              change_source=ReplayChangeEventSource([ChangeEvent("svc", "deployment", step=301)]))
    rng = random.Random(0)
    mgr.warm_up([_normal(rng) for _ in range(600)])
    return mgr


def test_async_decisions_match_sync_when_awaited():
    sync, asyn = _lazy_manager(), _lazy_manager(async_decisions=True)
    sync_alarms, async_alarms = [], []
    for x in _shifted_stream():
        sync_alarms.append(sync.process(x).alarm)
        async_alarms.append(asyn.process(x).alarm)
        if asyn.phase == "deciding":
            asyn.wait_for_decision(timeout=60)
    assert async_alarms == sync_alarms
    assert [d["verdict"] for d in asyn.decisions] == [d["verdict"] for d in sync.decisions]


def test_async_decisions_keep_serving_while_the_challenger_is_evaluated():
    mgr = _lazy_manager(async_decisions=True)
    for x in _shifted_stream():
        mgr.process(x)
    mgr.wait_for_decision(timeout=60)
    assert mgr.decisions and mgr.decisions[0]["action"] == "promote"
    # The serving loop only paid for the swap, not for evaluating the challenger.
    assert max(mgr.transition_ms) < max(mgr.decision_ms)


def test_cadal_runs_end_to_end_on_the_smoothed_pca_detector():
    from src.hst_model import detector_config
    mgr = DynamicModelManager("svc", _cfg(), detector_config("pca_s5"),
                              change_source=ReplayChangeEventSource([ChangeEvent("svc", "deployment", step=301)]))
    rng = random.Random(0)
    mgr.warm_up([_normal(rng) for _ in range(600)])
    assert mgr.model.base.axes is not None
    results = _run(mgr, _shifted_stream())
    promote = [d for d in mgr.decisions if d["action"] == "promote"]
    assert promote, mgr.decisions
    assert sum(r.alarm for r in results[-300:]) / 300 < 0.2
    assert mgr.registry.production().state.extra["inner"]["axes"]


def test_pot_threshold_method_sets_r0_and_fits_the_raw_error_tail():
    from dataclasses import replace as dc_replace
    from src.hst_model import detector_config
    from src.lifecycle_manager import calibrated_threshold

    cfg = _cfg(threshold_method="pot", pot_q=0.01)
    assert cfg.target_rate == 0.01
    mgr = DynamicModelManager("svc", cfg, detector_config("pca_s5"))
    rng = random.Random(0)
    mgr.warm_up([_normal(rng) for _ in range(1200)])
    assert 0.0 < mgr.threshold < 1.0
    calib = [mgr.model.score_one(_normal(rng)) for _ in range(500)]
    pct = calibrated_threshold(mgr.model, calib, dc_replace(cfg, threshold_method="percentile"))
    pot = calibrated_threshold(mgr.model, calib, cfg)
    assert pot != pct and 0.0 < pot < 1.0


# -- operator in the loop (CADAL-HITL) -------------------------------------------------------
def _hitl_manager(**kw):
    from src.change_events import QueueChangeEventSource
    from src.publishers import RecordingPublisher
    cfg = _cfg(operator_queries=True, query_ttl=400, query_budget=2, query_budget_window=5000,
               query_cooldown=1000, **kw)
    pub = RecordingPublisher()
    mgr = DynamicModelManager("svc", cfg, HST, change_source=QueueChangeEventSource(), publisher=pub)
    rng = random.Random(0)
    mgr.warm_up([_normal(rng) for _ in range(600)])
    return mgr, pub


def _silent_regime_change(seed=3, before=300, after=900):
    """A shift re-baselining cannot repair (a and b swap roles) and that no event explains."""
    rng = random.Random(seed)
    rows = [_normal(rng) for _ in range(before)]
    for _ in range(after):
        r = _normal(rng)
        r["a"], r["b"] = 0.75 + rng.gauss(0, 0.04), 0.05 + rng.gauss(0, 0.02)
        rows.append(r)
    return rows


def _run_until_query(mgr):
    for x in _silent_regime_change():
        mgr.process(x)
        if mgr.open_queries:
            return mgr.open_queries[0]
    return None


def test_ambiguous_shift_asks_the_operator_and_keeps_the_champion():
    mgr, pub = _hitl_manager(rebaseline=False)
    q = _run_until_query(mgr)
    assert q is not None, mgr.decisions
    assert mgr.decisions[-1]["action"] == "ask" and mgr.decisions[-1]["query_id"] == q["query_id"]
    assert mgr.registry.production().version == 1      # nothing replaced yet
    assert any(p["event"] == "operator_query" for p in pub.payloads)
    assert "_candidate" not in q                       # public view carries no model


def test_answer_new_normal_promotes_the_validated_candidate_with_an_audited_reason():
    mgr, pub = _hitl_manager(rebaseline=False)
    q = _run_until_query(mgr)
    decision = mgr.answer_query(q["query_id"], "new_normal", operator="shalon")
    assert decision["action"] == "promote" and decision["query_id"] == q["query_id"]
    prod = mgr.registry.production()
    assert prod.version > 1 and prod.tags["query_id"] == q["query_id"] and prod.tags["operator"] == "shalon"
    last = mgr.registry.transitions[-1]
    assert last.transition == "promote" and q["query_id"] in last.reason
    assert mgr.queries[q["query_id"]]["status"] == "answered"
    assert any(p["event"] == "query_answered" for p in pub.payloads)


def test_answer_incident_keeps_the_champion_and_pauses_asking():
    mgr, _ = _hitl_manager(rebaseline=False)
    q = _run_until_query(mgr)
    decision = mgr.answer_query(q["query_id"], "incident")
    assert decision["action"] == "hold" and mgr.registry.production().version == 1
    assert not mgr._may_ask()
    import pytest as _pt
    with _pt.raises(KeyError):
        mgr.answer_query(q["query_id"], "new_normal")   # already answered


def test_unanswered_query_expires_to_hold():
    mgr, pub = _hitl_manager(rebaseline=False)
    q = _run_until_query(mgr)
    rng = random.Random(9)
    for _ in range(mgr.cfg.query_ttl + 5):
        mgr.process(_normal(rng))
    assert mgr.queries[q["query_id"]]["status"] == "expired"
    assert any(d["trigger"] == "operator_timeout" for d in mgr.decisions)
    assert mgr.registry.production().version == 1


def test_expired_query_pauses_asking_like_an_incident_answer():
    mgr, _ = _hitl_manager(rebaseline=False)
    _run_until_query(mgr)
    rng = random.Random(9)
    for _ in range(mgr.cfg.query_ttl + 5):
        mgr.process(_normal(rng))
    assert not mgr.open_queries and not mgr._may_ask()
    assert mgr._ask_cooldown_until > mgr.step


def test_only_one_query_is_open_per_service():
    mgr, _ = _hitl_manager(rebaseline=False)
    _run_until_query(mgr)
    assert not mgr._may_ask()                    # the open question blocks a second one
    mgr._query_steps = []                        # even with budget to spare
    assert not mgr._may_ask()


def test_query_budget_caps_how_often_the_operator_is_asked():
    mgr, _ = _hitl_manager(rebaseline=False)
    mgr._query_steps = [mgr.step, mgr.step]   # budget of 2 already used in this window
    assert not mgr._may_ask()
    assert _run_until_query(mgr) is None


def test_without_operator_queries_the_same_shift_is_held():
    mgr, _ = _hitl_manager(rebaseline=False)
    mgr.cfg = LifecycleConfig(**{**mgr.cfg.__dict__, "operator_queries": False})
    assert _run_until_query(mgr) is None
    assert all(d["action"] != "ask" for d in mgr.decisions)


def test_manual_rollback_and_validity_check_are_audited():
    mgr, _ = _hitl_manager(rebaseline=False)
    q = _run_until_query(mgr)
    mgr.answer_query(q["query_id"], "new_normal")
    promoted = mgr.registry.production().version
    d = mgr.manual_set_version(1, "rollback", operator="shalon")
    assert d["action"] == "rollback" and mgr.registry.production().version == 1
    assert mgr.registry.transitions[-1].evidence["operator"] == "shalon"
    assert "target_recent_alarm_rate" in mgr.registry.transitions[-1].evidence
    assert mgr.request_validity_check() is True and mgr.phase == "quarantine"
    assert mgr.request_validity_check() is False     # already observing
    assert promoted > 1


# ── sequential early stop ────────────────────────────────────────────────────────────────────────
def _early_cfg(**kw):
    return _cfg(early_stop=True, quarantine_with_change=400, quarantine_silent=400, **kw)


def test_early_stop_promotes_a_deployment_level_shift_before_the_full_quarantine():
    pub = RecordingPublisher()
    mgr = _manager(_early_cfg(), events=[ChangeEvent("svc", "deployment", step=301)], publisher=pub)
    results = _run(mgr, _shifted_stream())
    promote = next(d for d in mgr.decisions if d["action"] == "promote")
    ev = promote["evidence"]
    assert ev["early"] and ev["repair"] == "rebaseline"
    assert ev["quarantine_events"] < ev["quarantine_length"] == 400
    assert "decided early" in promote["reason"]
    looks = [p for p in pub.payloads if p.get("event") == "quarantine_look"]
    assert looks and looks[-1]["conclusive"] and looks[-1]["seen"] == ev["quarantine_events"]
    assert sum(r.alarm for r in results[-300:]) / 300 < 0.15


def test_without_early_stop_the_same_shift_waits_the_full_quarantine():
    mgr = _manager(_cfg(quarantine_with_change=400), events=[ChangeEvent("svc", "deployment", step=301)])
    _run(mgr, _shifted_stream())
    promote = next(d for d in mgr.decisions if d["action"] == "promote")
    assert promote["evidence"]["early"] is False and promote["evidence"]["quarantine_events"] == 400


def test_early_stop_never_promotes_a_silent_shift():
    mgr = _manager(_early_cfg())
    _run(mgr, _shifted_stream())
    assert mgr.decisions
    assert not any(d["action"] == "promote" and d["evidence"].get("early") for d in mgr.decisions)


def test_early_stop_never_learns_a_transient_burst():
    rng = random.Random(5)
    rows = [_normal(rng) for _ in range(300)]
    rows += [{f: rng.random() for f in FEATURES} for _ in range(60)]
    rows += [_normal(rng) for _ in range(900)]
    mgr = _manager(_early_cfg())
    _run(mgr, rows)
    assert all(d["action"] != "promote" for d in mgr.decisions)
    assert mgr.registry.production().version == 1


def test_async_early_looks_match_sync_and_report_progress():
    events = [ChangeEvent("svc", "deployment", step=301)]
    sync, asyn = _manager(_early_cfg(), events=events), _manager(_early_cfg(async_decisions=True), events=events)
    progress = []
    for x in _shifted_stream():
        sync.process(x)
        asyn.process(x)
        if asyn.quarantine_progress():
            progress.append(asyn.quarantine_progress())
        if asyn._pending is not None:
            asyn.wait_for_decision(timeout=60)
    summary = lambda m: [(d["verdict"], d["evidence"].get("early"), d["evidence"].get("quarantine_events"))
                         for d in m.decisions]
    assert summary(asyn) == summary(sync)
    assert any(early and verdict == "concept_drift" for verdict, early, _ in summary(asyn))
    assert progress and progress[0]["length"] == 400 and progress[0]["looks"] == [200, 300]
    assert asyn.quarantine_progress() is None
