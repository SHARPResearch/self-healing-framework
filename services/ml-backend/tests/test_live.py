"""
Live mode without a cluster: a fake Prometheus behind OnlineBoutiqueTelemetry, the LiveFleet,
the scrape step, the deployment watcher fan-out and the API's live/replay guards.
"""

import random

import pytest
from fastapi.testclient import TestClient

from app.config import settings

settings.start_replay = False
settings.use_backing_services = False

import app.core.pipeline_path  # noqa: F401,E402
from src.change_events import change_event_from_k8s  # noqa: E402

from app.live import ChangeFanOut, LiveFleet, display_name, live_samples_per_day  # noqa: E402
from app.main import app  # noqa: E402
from app.prom import FEATURES, OnlineBoutiqueTelemetry, feature_queries  # noqa: E402
from app.runtime import runtime  # noqa: E402
from app.store import MemoryStore  # noqa: E402

SERVICES = ["cartservice", "paymentservice"]
BASE = {"cpu_rate": 0.05, "memory_used": 6e7, "network_rx": 2e4, "network_tx": 3e4,
        "cpu_throttled": 0.01, "restarts": 0.0, "ready_ratio": 1.0}


class FakePrometheus:
    """Answers the seven feature queries (and discovery) like Prometheus does."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.queries = {q: f for f, q in feature_queries(settings.k8s_namespace).items()}
        self.spike = set()
        self.t = 1_700_000_000.0

    def _value(self, feature, app):
        v = BASE[feature] * (1 + self.rng.gauss(0, 0.05)) if BASE[feature] else 0.0
        if app in self.spike and feature == "cpu_rate":
            v *= 20
        return v

    def query(self, promql):
        if promql.startswith("kube_deployment_spec_replicas"):
            return [{"metric": {"deployment": d}, "value": [self.t, "1"]} for d in SERVICES + ["loadgenerator"]]
        feature = self.queries[promql]
        out = []
        for app in SERVICES:
            if feature == "cpu_throttled" and app == "paymentservice":
                out.append({"metric": {"app": app}, "value": [self.t, "NaN"]})   # 0/0 at a scrape
            else:
                out.append({"metric": {"app": app}, "value": [self.t, str(self._value(feature, app))]})
        return out

    def query_range(self, promql, start, end, step_s):
        feature = self.queries[promql]
        n = int((end - start).total_seconds() / step_s)
        return [{"metric": {"app": app},
                 "values": [[start.timestamp() + i * step_s, str(self._value(feature, app))] for i in range(n)]}
                for app in SERVICES]


@pytest.fixture()
def prom():
    return FakePrometheus()


def test_queries_map_pods_to_apps_and_cover_every_feature():
    q = feature_queries("online-boutique")
    assert set(q) == set(FEATURES)
    assert all('namespace="online-boutique"' in v for v in q.values())
    assert 'label_replace' in q["cpu_rate"] and '"pod"' in q["cpu_rate"]
    assert '"deployment"' in q["ready_ratio"]


def test_telemetry_excludes_the_load_generator_and_fills_gaps(prom):
    tel = OnlineBoutiqueTelemetry(prom, "online-boutique")
    assert tel.services() == SERVICES
    hist = tel.history(SERVICES, minutes=5, step_s=5)
    assert len(hist["cartservice"]) == 60 and set(hist["cartservice"][0]) == set(FEATURES)
    row = tel.latest(SERVICES)["paymentservice"]
    assert row["cpu_throttled"] == hist["paymentservice"][-1]["cpu_throttled"]   # NaN forward-filled


def test_display_names():
    assert display_name("cartservice") == "Cart Service"
    assert display_name("productcatalogservice") == "Product Catalog Service"
    assert display_name("redis-cart") == "Redis Cart"


@pytest.fixture()
def client(prom, monkeypatch):
    monkeypatch.setattr(settings, "live_warmup_minutes", 40)
    monkeypatch.setattr(settings, "live_min_warmup_minutes", 10)
    runtime.fleet = LiveFleet(OnlineBoutiqueTelemetry(prom, settings.k8s_namespace))
    runtime.store = MemoryStore()
    runtime.hub.take()
    runtime._alarms.clear()
    with TestClient(app) as c:
        yield c


def test_live_fleet_scores_scrapes_and_alarms_on_a_spike(client, prom):
    health = client.get("/api/health").json()
    assert health["mode"] == "prometheus"
    ids = [s["serviceId"] for s in client.get("/api/services").json()]
    assert ids == SERVICES
    assert client.get("/api/services").json()[0]["source"] == "online-boutique/cartservice"
    for _ in range(20):
        client.portal.call(runtime.scrape_once)
    assert all(not s["alarm"] for s in client.get("/api/services").json())
    prom.spike.add("paymentservice")
    for _ in range(5):
        client.portal.call(runtime.scrape_once)
    svc = {s["serviceId"]: s for s in client.get("/api/services").json()}
    assert svc["paymentservice"]["alarm"] and not svc["cartservice"]["alarm"]
    assert runtime.fleet.cfg.quarantine_silent == live_samples_per_day()


def test_replay_controls_are_rejected_in_live_mode(client):
    assert client.post("/api/demo/cartservice/deploy").status_code == 409
    assert client.post("/api/demo/speed", json={"eventsPerSec": 120}).status_code == 409
    assert client.post("/api/live/cartservice/explode").status_code == 422
    # no cluster in tests: the Kubernetes API was never connected
    assert client.post("/api/live/cartservice/cpu_stress").status_code == 503


def _deployment(name, generation, observed):
    return {"type": "MODIFIED", "object": {
        "metadata": {"name": name, "namespace": "online-boutique", "labels": {"app": name},
                     "generation": generation},
        "spec": {"replicas": 1, "template": {"spec": {"containers": [{"image": f"{name}:v2"}]}}},
        "status": {"observedGeneration": observed}}}


class FakeWatcher:
    def __init__(self, events):
        self.events = events

    def poll(self, step):
        out, self.events = self.events, []
        return out


def test_rollouts_are_routed_to_the_right_service_only(client):
    fan = ChangeFanOut("online-boutique")
    fan.watcher = FakeWatcher([change_event_from_k8s(_deployment("cartservice", 3, 2)),
                               change_event_from_k8s(_deployment("cartservice", 3, 2)),   # same rollout again
                               change_event_from_k8s(_deployment("loadgenerator", 5, 4))])
    routed = fan.route(runtime.fleet)
    assert [e.service_id for e in routed] == ["cartservice"]
    assert runtime.fleet.services["cartservice"].changes.poll(0)
    assert not runtime.fleet.services["paymentservice"].changes.poll(0)
