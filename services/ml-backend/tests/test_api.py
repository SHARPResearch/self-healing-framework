"""
API tests: the real app on in-memory fallbacks (no Docker), two demo services replaying the same
calm SMD windows the live demo uses (machine-1-2 from row 9250, machine-2-2 from row 0).

The replay loop is off; tests advance the fleet themselves with runtime.step_all() on the client's
event loop, so every lifecycle outcome is deterministic.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings

settings.start_replay = False
settings.use_backing_services = False

from app.fleet import ServiceFleet  # noqa: E402
from app.main import app  # noqa: E402
from app.runtime import runtime  # noqa: E402

SERVICE = "service-test"
INCIDENT_SERVICE = "service-incident"
SERVICE_HEALTH_KEYS = {"serviceId", "displayName", "status", "anomalyScore", "scoreHistory",
                       "lastAction", "lastActionAt", "driftDetected"}
MODEL_RUN_KEYS = {"runId", "entityId", "serviceName", "version", "stage", "modelType",
                  "driftLibrary", "updatedAt", "params", "metrics"}


@pytest.fixture()
def client():
    runtime.fleet = ServiceFleet([(SERVICE, "Test Service", "machine-1-2", 9250),
                                  (INCIDENT_SERVICE, "Incident Service", "machine-2-2", 0)])
    with TestClient(app) as c:
        yield c


def step(client):
    # a live decision takes ~40 ms (~2 events); without the wait the test would race past it
    for rt in runtime.fleet.services.values():
        if rt.manager.phase == "deciding":
            rt.manager.wait_for_decision(timeout=60)
    client.portal.call(runtime.step_all)


def run_until_decision(client, actions, service=SERVICE, max_events=None):
    """Advance the replay until the service's latest decision is one of `actions`."""
    rt = runtime.fleet.services[service]
    max_events = max_events or settings.demo_samples_per_day * 4
    for _ in range(max_events):
        step(client)
        if rt.manager.decisions and rt.manager.decisions[-1]["action"] in actions:
            rt.manager.wait_for_decision(timeout=60)
            client.portal.call(runtime.drain_all)
            return rt.manager.decisions[-1]
    raise AssertionError(f"no {actions} decision within {max_events} events")


def warm(client, n=200):
    for _ in range(n):
        step(client)


def test_health_reports_fallback_store(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["store"] == "memory" and body["redis"] is False
    assert body["services"] == 2


def test_services_match_frontend_service_health(client):
    warm(client, 50)
    rows = client.get("/api/services").json()
    assert len(rows) == 2
    assert SERVICE_HEALTH_KEYS <= rows[0].keys()
    assert rows[0]["status"] in {"watch", "warn", "degrade", "critical"}
    assert 0.0 <= rows[0]["anomalyScore"] <= 1.0
    scores = client.get(f"/api/services/{SERVICE}/scores?limit=20").json()
    assert len(scores) == 20 and scores[-1]["threshold"] == 0.5


def test_models_match_frontend_model_run(client):
    rows = client.get("/api/models").json()
    assert MODEL_RUN_KEYS <= rows[0].keys()
    assert rows[0]["modelType"] == "PCA" and rows[0]["thresholdMethod"] == "pot"
    detail = client.get(f"/api/models/{SERVICE}").json()
    assert detail["versions"][0]["status"] == "production"


def test_unknown_service_and_bad_answer_are_rejected(client):
    assert client.get("/api/models/nope").status_code == 404
    assert client.post("/api/demo/nope/deploy").status_code == 404
    assert client.post("/api/queries/q-x/answer", json={"answer": "maybe"}).status_code == 422
    assert client.post("/api/queries/q-x/answer", json={"answer": "incident"}).status_code == 404


def test_deploy_is_learned_and_can_be_rolled_back(client):
    warm(client)
    assert client.post(f"/api/demo/{SERVICE}/deploy").status_code == 200
    decision = run_until_decision(client, {"promote", "hold", "ask"})
    assert decision["action"] == "promote" and decision["trigger"] == "change_event"
    model = client.get(f"/api/models/{SERVICE}").json()
    assert model["productionVersion"] == 2
    rollback = client.post(f"/api/models/{SERVICE}/rollback", json={"operator": "tester"})
    assert rollback.status_code == 200
    assert rollback.json()["model"]["productionVersion"] == 1
    transitions = client.get(f"/api/models/{SERVICE}").json()["transitions"]
    assert transitions[-1]["transition"] == "rollback"


def test_quarantine_progress_and_early_looks_are_reported(client):
    warm(client)
    client.post(f"/api/demo/{SERVICE}/deploy")
    step(client)
    svc = next(s for s in client.get("/api/services").json() if s["serviceId"] == SERVICE)
    length = settings.demo_samples_per_day
    assert svc["quarantine"] == {"seen": svc["quarantine"]["seen"], "length": length,
                                 "looks": [length // 2, length * 3 // 4]}
    decision = run_until_decision(client, {"promote", "hold", "ask"})
    assert decision["evidence"]["quarantine_events"] <= decision["evidence"]["quarantine_length"] == length
    looks = client.get("/api/logs", params={"q": f"early look service:{SERVICE}"}).json()["lines"]
    assert any(f"early look at {length // 2} of {length} events" in ln["message"] for ln in looks)
    assert next(s for s in client.get("/api/services").json() if s["serviceId"] == SERVICE)["quarantine"] is None


def test_silent_change_asks_the_operator_and_the_answer_promotes(client):
    warm(client)
    client.post(f"/api/demo/{SERVICE}/silent_change")
    decision = run_until_decision(client, {"promote", "hold", "ask"})
    assert decision["verdict"] == "ambiguous" and decision["action"] == "ask"
    open_queries = client.get("/api/queries?status=open").json()
    assert len(open_queries) == 1
    qid = open_queries[0]["queryId"]
    answered = client.post(f"/api/queries/{qid}/answer",
                           json={"answer": "new_normal", "operator": "tester"})
    assert answered.status_code == 200
    assert answered.json()["decision"]["action"] == "promote"
    versions = client.get(f"/api/models/{SERVICE}").json()["versions"]
    promoted = [v for v in versions if v["status"] == "production"][0]
    assert promoted["queryId"] == qid and promoted["operator"] == "tester"
    # answering twice is a conflict, not a second promotion
    again = client.post(f"/api/queries/{qid}/answer", json={"answer": "new_normal"})
    assert again.status_code == 409


def test_incident_is_never_learned(client):
    warm(client)
    client.post(f"/api/demo/{INCIDENT_SERVICE}/incident")
    decision = run_until_decision(client, {"promote", "hold", "ask", "resume"}, service=INCIDENT_SERVICE)
    assert decision["action"] in {"hold", "resume"}
    assert client.get(f"/api/models/{INCIDENT_SERVICE}").json()["productionVersion"] == 1


def test_websocket_sends_snapshot_then_live_events(client):
    with client.websocket_connect("/ws/events") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        assert first["data"]["services"][0]["serviceId"] == SERVICE
        client.post(f"/api/demo/{SERVICE}/incident")
        seen = ws.receive_json()
        assert seen["type"] == "demo_injection" and seen["service_id"] == SERVICE
