from src.drift_attribution import Action, QuarantineEvidence, Verdict, attribute

R0 = 0.03


def _ev(**kw):
    base = dict(
        trigger="drift_up", target_rate=R0, champion_alarm_rate=0.5,
        champion_tail_alarm_rate=0.5, challenger_tail_alarm_rate=0.03, change_event_id=None,
    )
    base.update(kw)
    return QuarantineEvidence(**base)


def test_persistent_learnable_shift_is_concept_drift_and_promotes():
    a = attribute(_ev())
    assert a.verdict is Verdict.CONCEPT_DRIFT
    assert a.action is Action.PROMOTE
    assert "no explaining change event" in a.reason


def test_persistent_but_unlearnable_shift_is_an_incident_and_holds():
    a = attribute(_ev(challenger_tail_alarm_rate=0.4))
    assert a.verdict is Verdict.INCIDENT
    assert a.action is Action.HOLD


def test_transient_shift_is_no_change():
    a = attribute(_ev(champion_alarm_rate=0.3, champion_tail_alarm_rate=0.02))
    assert a.verdict is Verdict.NO_CHANGE
    assert a.action is Action.RESUME


def test_change_event_lowers_the_persistence_required():
    # Tail alarm rate 0.09 = 3 x r0: below the silent stale line (4 x) but above the
    # change-explained line (2 x).
    silent = attribute(_ev(champion_tail_alarm_rate=0.09))
    explained = attribute(_ev(champion_tail_alarm_rate=0.09, change_event_id="svc:deployment@10"))
    assert silent.verdict is Verdict.NO_CHANGE
    assert explained.verdict is Verdict.CONCEPT_DRIFT
    assert "svc:deployment@10" in explained.reason


def test_downward_collapse_is_model_decay_and_rolls_back():
    a = attribute(_ev(trigger="drift_down", champion_alarm_rate=0.001, champion_tail_alarm_rate=0.0))
    assert a.verdict is Verdict.MODEL_DECAY
    assert a.action is Action.ROLLBACK


def test_downward_shift_with_healthy_alarm_rate_is_not_decay():
    a = attribute(_ev(trigger="drift_down", champion_alarm_rate=0.03, champion_tail_alarm_rate=0.03))
    assert a.verdict is Verdict.NO_CHANGE


def test_missing_challenger_defaults_to_the_safe_incident_verdict():
    a = attribute(_ev(challenger_tail_alarm_rate=None))
    assert a.verdict is Verdict.INCIDENT


def test_evidence_is_recorded_for_the_audit_trail():
    a = attribute(_ev(change_event_id="x"))
    assert a.evidence["change_event_id"] == "x"
    assert a.evidence["stale_line"] == round(2.0 * R0, 4)
    assert a.evidence["trigger"] == "drift_up"


def test_small_tails_get_binomial_slack_on_the_learnable_line():
    # 0.11 on a 40 event tail is 4 or 5 alarms vs an expected ~1: noise, not a failed regime.
    noisy = _ev(challenger_tail_alarm_rate=0.11, n_tail=40)
    assert attribute(noisy).verdict is Verdict.CONCEPT_DRIFT
    assert attribute(_ev(challenger_tail_alarm_rate=0.11)).verdict is Verdict.INCIDENT
    # The slack shrinks with more evidence.
    assert attribute(_ev(challenger_tail_alarm_rate=0.11, n_tail=5000)).verdict is Verdict.INCIDENT


def test_tail_leaving_the_fitted_support_is_an_incident_even_if_challenger_scores_it_normal():
    a = attribute(_ev(challenger_tail_alarm_rate=0.01, tail_out_of_support_rate=0.6, n_tail=200))
    assert a.verdict is Verdict.INCIDENT
    assert "outside the range" in a.reason
    ok = attribute(_ev(challenger_tail_alarm_rate=0.01, tail_out_of_support_rate=0.02, n_tail=200))
    assert ok.verdict is Verdict.CONCEPT_DRIFT


def test_entity_null_floors_raise_the_stationarity_lines():
    # On an entity whose normal windows already show challenger tail rates of 0.3, a tail rate
    # of 0.2 is ordinary, not evidence of an incident.
    ev = dict(challenger_tail_alarm_rate=0.2, tail_out_of_support_rate=0.7, n_tail=144)
    assert attribute(_ev(**ev)).verdict is Verdict.INCIDENT
    floored = attribute(_ev(**ev, learnable_floor=0.3, moving_floor=0.8))
    assert floored.verdict is Verdict.CONCEPT_DRIFT
    assert floored.evidence["learnable_line"] == 0.3 and floored.evidence["moving_line"] == 0.8
