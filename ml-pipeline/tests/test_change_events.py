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


# ── restarts ──────────────────────────────────────────────────────────────────────────────────────
from datetime import datetime, timedelta, timezone  # noqa: E402

from src.change_events import PodRestartTracker  # noqa: E402

T0 = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def _pod(name, template="abc", created=T0 - timedelta(hours=1), restarts=0, reason=None, event_type="ADDED"):
    status = {"containerStatuses": [{"name": "server", "restartCount": restarts,
                                     "lastState": {"terminated": {"reason": reason}} if reason else {}}]}
    return {"type": event_type, "object": {
        "metadata": {"name": name, "labels": {"app": "cartservice", "pod-template-hash": template},
                     "creationTimestamp": created.isoformat()},
        "status": status}}


def test_existing_pods_are_learned_not_reported():
    tracker = PodRestartTracker(started_at=T0)
    assert tracker.observe(_pod("cart-abc-1")) == []
    assert tracker.observe(_pod("cart-abc-1", event_type="MODIFIED")) == []


def test_a_replacement_pod_from_the_same_template_is_a_restart():
    tracker = PodRestartTracker(started_at=T0)
    tracker.observe(_pod("cart-abc-1"))
    events = tracker.observe(_pod("cart-abc-2", created=T0 + timedelta(minutes=5)))
    assert [(e.kind, e.service_id, e.detail["reason"]) for e in events] == [("restart", "cartservice", "pod_replaced")]


def test_a_pod_from_a_new_template_is_a_rollout_not_a_restart():
    tracker = PodRestartTracker(started_at=T0)
    tracker.observe(_pod("cart-abc-1"))
    assert tracker.observe(_pod("cart-def-1", template="def", created=T0 + timedelta(minutes=5))) == []


def test_a_container_restart_is_reported_with_its_exit_reason():
    tracker = PodRestartTracker(started_at=T0)
    tracker.observe(_pod("cart-abc-1"))
    events = tracker.observe(_pod("cart-abc-1", restarts=1, reason="OOMKilled", event_type="MODIFIED"))
    assert len(events) == 1 and events[0].detail["reason"] == "container_restart"
    assert events[0].detail["exit_reason"] == "OOMKilled" and events[0].detail["restart_count"] == 1
    assert tracker.observe(_pod("cart-abc-1", restarts=1, reason="OOMKilled", event_type="MODIFIED")) == []
