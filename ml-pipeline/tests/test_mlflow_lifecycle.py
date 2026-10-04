import json

import mlflow
import pandas as pd
import pytest

from src.config import HSTConfig
from src.hst_model import build_model
from src.hst_state import capture, feature_names
from src.mlflow_lifecycle import InMemoryRegistry, MLflowRegistry

CFG = HSTConfig(n_trees=3, height=4, window_size=10, seed=3)


def _trained(n=30, offset=0.0):
    model = build_model(CFG)
    for i in range(n):
        model.learn_one({"a": (i % 7) / 10 + offset, "b": (i % 3) / 10})
    return model


def test_production_history_and_rollback_target(tmp_path):
    audit = tmp_path / "audit.jsonl"
    reg = InMemoryRegistry("svc", audit_path=audit)
    v1 = reg.register(capture(_trained()), 0.4, 0.03, step=0, reason="warm-up")
    reg.set_production(v1, step=0, transition="promote", reason="initial")
    v2 = reg.register(capture(_trained(offset=0.2)), 0.5, 0.03, step=100, reason="challenger")
    reg.set_production(v2, step=100, transition="promote", reason="concept drift",
                       evidence={"verdict": "concept_drift"})

    assert reg.production().version == v2
    assert reg.get(v1).status == "archived"
    assert reg.previous_production().version == v1
    assert [t.transition for t in reg.transitions] == ["register", "promote", "register", "promote"]
    assert reg.transitions[-1].evidence == {"verdict": "concept_drift"}

    lines = [json.loads(line) for line in audit.read_text().splitlines()]
    assert len(lines) == 4
    assert lines[-1]["entity_id"] == "svc" and lines[-1]["to_version"] == v2


def test_previous_production_is_none_with_a_single_version():
    reg = InMemoryRegistry("svc")
    v1 = reg.register(capture(_trained()), 0.4, 0.03, step=0, reason="warm-up")
    reg.set_production(v1, step=0, transition="promote", reason="initial")
    assert reg.previous_production() is None


def test_checkpoint_registers_and_serves_a_stable_version():
    reg = InMemoryRegistry("svc")
    v1 = reg.register(capture(_trained()), 0.4, 0.03, step=0, reason="warm-up")
    reg.set_production(v1, step=0, transition="promote", reason="initial")
    v2 = reg.checkpoint(capture(_trained(40)), 0.4, 0.03, step=500, reason="healthy")
    assert reg.production().version == v2
    assert reg.get(v2).tags["kind"] == "stable_checkpoint"
    assert reg.transitions[-1].transition == "checkpoint"


def test_production_lookup_fails_before_any_promotion():
    with pytest.raises(LookupError):
        InMemoryRegistry("svc").production()


def test_mlflow_registry_mirrors_versions_aliases_and_loads_as_pyfunc(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    uri = f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("component2_test")
    m1, m2 = _trained(), _trained(offset=0.2)
    params = {"n_trees": CFG.n_trees, "height": CFG.height, "window_size": CFG.window_size, "seed": CFG.seed}
    with mlflow.start_run():
        reg = MLflowRegistry("svc", uri, hst_params=params, feature_names=feature_names(m1))
        v1 = reg.register(capture(m1), 0.4, 0.03, step=0, reason="warm-up")
        reg.set_production(v1, step=0, transition="promote", reason="initial")
        v2 = reg.register(capture(m2), 0.55, 0.03, step=50, reason="challenger")
        reg.set_production(v2, step=50, transition="promote", reason="concept drift")

        mlflow_version, state, threshold = reg.sync_production()
        assert threshold == 0.55
        assert state.masses == capture(m2).masses

        client = mlflow.tracking.MlflowClient(uri)
        assert client.get_model_version("hst-svc", reg._mlflow_version[v1]).tags["status"] == "archived"
        assert client.get_model_version_by_alias("hst-svc", "production").version == mlflow_version

    probe = pd.DataFrame([{"a": 0.1, "b": 0.1}, {"a": 0.9, "b": 0.0}])
    loaded = mlflow.pyfunc.load_model("models:/hst-svc@production")
    assert loaded.predict(probe) == [min(max(m2.score_one(r), 0.0), 1.0) for r in probe.to_dict("records")]
