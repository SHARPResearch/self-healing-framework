"""
Logs page backend: the filter grammar, docker line parsing, alarm episodes, and the /api/logs
routes on the in-memory store (no Docker).
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings

settings.start_replay = False
settings.use_backing_services = False

from app.fleet import ServiceFleet  # noqa: E402
from app.logs import AlarmLog, container_level, make_line, parse_docker_line  # noqa: E402
from app.main import app  # noqa: E402
from app.runtime import runtime  # noqa: E402
from app.store import MemoryStore, parse_log_filter  # noqa: E402

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def line(service, message, level="info", source="container", offset=0, service_id=None):
    return make_line(service, message, level, source, service_id=service_id,
                     time=NOW + timedelta(seconds=offset))


def test_filter_grammar_splits_terms_from_free_text():
    f = parse_log_filter("checkpoint service:TimescaleDB level:error level:warn @source:container")
    assert f == {"text": ["checkpoint"], "service": ["timescaledb"], "level": ["error", "warn"],
                 "source": ["container"]}
    # an unknown key is just text, and a bare colon is not a term
    assert parse_log_filter("host:db1 :")["text"] == ["host:db1", ":"]


def test_docker_timestamps_are_parsed_to_microseconds():
    t, msg = parse_docker_line("2026-10-18T12:16:31.027613456Z 1:M 18 Oct * Saving...")
    assert t == datetime(2026, 10, 18, 12, 16, 31, 27613, tzinfo=timezone.utc)
    assert msg == "1:M 18 Oct * Saving..."
    assert parse_docker_line("Error response from daemon: No such container") == (
        None, "Error response from daemon: No such container")


def test_container_levels():
    assert container_level("2026-10-18 LOG:  checkpoint starting: time") == "info"
    assert container_level("FATAL:  password authentication failed") == "error"
    assert container_level("WARNING:  could not open statistics file") == "warn"
    assert container_level("1:M 18 Oct 2026 # Possible SECURITY ATTACK detected") == "warn"


def test_alarm_log_collapses_an_episode_into_two_lines_and_ignores_blips():
    a = AlarmLog()
    events = []
    for step in range(1, 300):
        alarm = 50 <= step < 70 or step == 75 or 150 <= step < 157   # burst, stray, a 7 event blip
        e = a.update(step, alarm, 0.9 if alarm else 0.1)
        if e:
            events.append((step, e[0]))
    assert events == [(57, "raised"), (75 + AlarmLog.QUIET, "cleared")]


def test_identical_lines_have_the_same_id_so_replays_do_not_duplicate():
    a, b = line("Redis", "DB saved on disk"), line("Redis", "DB saved on disk")
    assert a["id"] == b["id"]
    store = MemoryStore()
    asyncio.run(store.write_logs([a, b]))
    assert len(store.logs) == 1


def test_memory_store_filters_pages_and_buckets():
    store = MemoryStore()
    lines = [line("Redis", f"saved {i}", offset=i) for i in range(30)]
    lines += [line("TimescaleDB", "checkpoint complete", offset=40),
              line("TimescaleDB", "FATAL: out of memory", "error", offset=41),
              line("service-a-auth", "alarm raised", "warn", "lifecycle", 42, "service-a-auth")]
    asyncio.run(store.write_logs(lines))

    def q(*a, **k):
        return asyncio.run(store.query_logs(*a, **k))

    assert len(q("service:redis")) == 30
    assert [ln["message"] for ln in q("level:error")] == ["FATAL: out of memory"]
    assert [ln["service"] for ln in q("service:service-a-auth")] == ["service-a-auth"]
    assert len(q("CHECKPOINT")) == 1                     # case insensitive
    page = q("service:redis", limit=10)
    assert [ln["message"] for ln in page] == [f"saved {i}" for i in range(20, 30)]   # newest, oldest first
    older = q("service:redis", before=page[0]["time"], limit=10)
    assert older[-1]["message"] == "saved 19"
    hist = asyncio.run(store.log_histogram("", NOW, NOW + timedelta(seconds=60)))
    assert sum(b["info"] + b["warn"] + b["error"] for b in hist["buckets"]) == 33
    assert sum(b["error"] for b in hist["buckets"]) == 1


@pytest.fixture()
def client():
    runtime.fleet = ServiceFleet([("service-test", "Test Service", "machine-1-2", 9250)])
    runtime.store = MemoryStore()                        # the runtime is a singleton: start clean
    runtime.hub.take()
    runtime._alarms.clear()
    with TestClient(app) as c:
        yield c


def test_startup_and_injection_show_up_on_the_logs_page(client):
    body = client.get("/api/logs").json()
    assert any("warm-up complete" in ln["message"] and ln["serviceId"] == "service-test"
               for ln in body["lines"])
    assert client.post("/api/demo/service-test/deploy").status_code == 200
    body = client.get("/api/logs?q=service:service-test injection").json()
    assert len(body["lines"]) == 1 and body["hasMore"] is False
    assert body["lines"][0]["message"].startswith("demo injection: deploy on ")
    assert body["lines"][0]["source"] == "lifecycle"


def test_logs_routes_filter_limit_and_summarise(client):
    client.post("/api/demo/service-test/incident")
    assert client.get("/api/logs?level=error").status_code == 200
    only_warn = client.get("/api/logs", params={"q": "level:warn"}).json()["lines"]
    assert all(ln["level"] == "warn" for ln in only_warn)
    two = client.get("/api/logs", params={"limit": 1}).json()
    assert len(two["lines"]) == 1 and two["hasMore"] is True
    services = client.get("/api/logs/services").json()
    assert {"service": "service-test", "source": "lifecycle"}.items() <= next(
        s for s in services if s["service"] == "service-test").items()
    hist = client.get("/api/logs/histogram").json()
    assert hist["bucketSeconds"] >= 1 and sum(
        b["info"] + b["warn"] + b["error"] for b in hist["buckets"]) >= 2
    assert client.get("/api/logs", params={"limit": 0}).status_code == 422


def test_logs_are_streamed_over_the_websocket_but_not_to_the_redis_stream(client):
    with client.websocket_connect("/ws/events") as ws:
        assert ws.receive_json()["type"] == "snapshot"
        client.post("/api/demo/service-test/incident")
        client.get("/api/logs")                          # flushes the pending lines onto the bus
        seen = {ws.receive_json()["type"] for _ in range(2)}
    assert seen == {"demo_injection", "log"}


def test_reset_is_logged_and_drops_the_old_fleets_lifecycle_lines(client):
    client.post("/api/demo/service-test/incident")
    assert client.get("/api/logs", params={"q": "injection"}).json()["lines"]
    assert client.post("/api/demo/reset").status_code == 200
    lines = client.get("/api/logs", params={"q": "reset"}).json()["lines"]
    assert any(ln["message"].startswith("demo reset") and ln["service"] == "ml-backend" for ln in lines)
    assert client.get("/api/logs", params={"q": "injection"}).json()["lines"] == []
    warm = client.get("/api/logs", params={"q": "warm-up complete service:service-test"}).json()["lines"]
    assert len(warm) == 1                              # the fresh fleet's, not the startup one


def test_reset_during_a_step_does_not_kill_the_replay(client, monkeypatch):
    # A step yields between services; a reset landing in that gap used to swap in a half-built
    # fleet under the step, which raised inside the replay task and stopped the demo silently.
    after_step = runtime._after_step

    async def yielding_after_step(*args, **kwargs):
        await asyncio.sleep(0)
        await after_step(*args, **kwargs)

    monkeypatch.setattr(runtime, "_after_step", yielding_after_step)

    async def step_and_reset():
        await asyncio.gather(runtime.step_all(), runtime.reset())

    client.portal.call(step_and_reset)
    tick = runtime.tick
    client.portal.call(runtime.step_all)
    assert runtime.tick == tick + 1 and not runtime.paused
