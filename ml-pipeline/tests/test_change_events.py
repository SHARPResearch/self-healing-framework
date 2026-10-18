from src.change_events import (
    ChangeEvent, NullChangeEventSource, ReplayChangeEventSource, change_event_from_k8s,
)


def test_replay_source_releases_each_event_once_when_due():
    src = ReplayChangeEventSource([
        ChangeEvent("svc", "deployment", step=10),
        ChangeEvent("svc", "config", step=5),
    ])
    assert src.poll(4) == []
    assert [e.kind for e in src.poll(5)] == ["config"]
    assert src.poll(9) == []
    assert [e.kind for e in src.poll(50)] == ["deployment"]
    assert src.poll(100) == []


def test_null_source_never_emits():
    assert NullChangeEventSource().poll(10_000) == []


def _deployment(event_type, generation, observed, replicas=2, last_replicas=None):
    annotations = {} if last_replicas is None else {"selfheal.io/last-replicas": str(last_replicas)}
    return {
        "type": event_type,
        "object": {
            "metadata": {
                "name": "order-svc", "namespace": "shop", "generation": generation,
                "labels": {"app": "order-service"}, "annotations": annotations,
            },
            "spec": {"replicas": replicas, "template": {"spec": {"containers": [{"image": "order:v2"}]}}},
            "status": {} if observed is None else {"observedGeneration": observed},
        },
    }


def test_k8s_spec_change_is_a_deployment_event():
    evt = change_event_from_k8s(_deployment("MODIFIED", generation=4, observed=3))
    assert evt.service_id == "order-service"
    assert evt.kind == "deployment"
    assert evt.detail["images"] == ["order:v2"]


def test_k8s_status_only_update_is_ignored():
    assert change_event_from_k8s(_deployment("MODIFIED", generation=4, observed=4)) is None


def test_k8s_replica_change_is_a_scale_event():
    evt = change_event_from_k8s(_deployment("MODIFIED", 5, 4, replicas=4, last_replicas=2))
    assert evt.kind == "scale"


def test_k8s_new_deployment_counts_as_deployment():
    assert change_event_from_k8s(_deployment("ADDED", 1, None)).kind == "deployment"


def test_event_id_is_stable_and_readable():
    assert ChangeEvent("svc", "deployment", step=42).event_id == "svc:deployment@42"


def test_queue_source_releases_pushed_events_once():
    from src.change_events import QueueChangeEventSource
    src = QueueChangeEventSource()
    assert src.poll(1) == []
    src.push(ChangeEvent("svc", "deployment", step=5))
    src.push(ChangeEvent("svc", "config", step=6))
    assert [e.kind for e in src.poll(7)] == ["deployment", "config"]
    assert src.poll(8) == []
