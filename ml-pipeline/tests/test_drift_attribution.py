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
