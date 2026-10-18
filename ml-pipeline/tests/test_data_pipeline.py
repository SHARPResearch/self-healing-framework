import numpy as np
import pandas as pd
import pytest

from src.data_pipeline import SCENARIOS, apply_injections, change_events_for, make_scenario


def _df(n=100):
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "a": rng.uniform(0, 0.5, n), "b": rng.uniform(0, 0.5, n),
        "c": rng.uniform(0, 0.5, n), "flat": np.zeros(n),
    })


def test_none_scenario_injects_nothing():
    assert make_scenario("none", _df(), "e") == []


def test_unknown_scenario_is_rejected():
    with pytest.raises(ValueError):
        make_scenario("nope", _df(), "e")


def test_deploy_and_silent_shift_the_same_features_but_differ_in_announcement():
    deploy = make_scenario("deploy", _df(), "e", feature_fraction=0.5)
    silent = make_scenario("silent", _df(), "e", feature_fraction=0.5)
    assert [i.features for i in deploy] == [i.features for i in silent]
    assert all(i.announced for i in deploy) and not any(i.announced for i in silent)
    assert all("flat" not in i.features for i in deploy)  # constant features are never shifted
    assert [i.start for i in deploy] == [35, 70]


def test_noop_deploy_announces_without_shifting():
    inj = make_scenario("noop_deploy", _df(), "e")
    assert all(i.announced and i.features == () for i in inj)
    pd.testing.assert_frame_equal(apply_injections(_df(), inj), _df())


def test_shift_applies_from_start_onward_and_stays_in_range():
    df = _df()
    inj = make_scenario("deploy", df, "e", starts=(0.5,), feature_fraction=0.34)
    out = apply_injections(df, inj)
    feat, delta = inj[0].features[0], inj[0].deltas[0]
    assert (out[feat].iloc[:50] == df[feat].iloc[:50]).all()
    assert np.allclose(out[feat].iloc[50:], np.clip(df[feat].iloc[50:] + delta, 0, 1))
    assert out.values.max() <= 1.0


def test_change_events_only_for_announced_injections():
    df = _df()
    assert [e.step for e in change_events_for(make_scenario("deploy", df, "e"), "e")] == [36, 71]
    assert change_events_for(make_scenario("silent", df, "e"), "e") == []


def test_scenarios_are_reproducible_per_entity_and_seed():
    df = _df()
    assert make_scenario("deploy", df, "e", seed=1) == make_scenario("deploy", df, "e", seed=1)
    assert make_scenario("deploy", df, "e", seed=1) != make_scenario("deploy", df, "f", seed=1)
    assert set(SCENARIOS) == {"none", "deploy", "silent", "noop_deploy"}
