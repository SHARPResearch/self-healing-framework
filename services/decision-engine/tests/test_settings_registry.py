"""
RuntimeSettings tests — validation, premium gating and live apply.

Pure logic: the Postgres calls are monkeypatched with an in-memory fake,
so no live DB is required. The scheduler is faked to assert reschedules.

Run with:
    cd services/decision-engine
    uv run pytest tests/test_settings_registry.py -v
"""
import pytest

from app.core.runtime_settings import RuntimeSettings, SETTINGS_SPEC


@pytest.fixture
def rs(monkeypatch):
    """A fresh RuntimeSettings with an in-memory settings store."""
    store: dict[str, object] = {}
    audit: list[tuple] = []

    async def fake_list():
        return dict(store)

    async def fake_save(key, value, actor="unknown"):
        store[key] = value

    async def fake_audit(key, old, new, actor="unknown"):
        audit.append((key, old, new, actor))

    import app.core.runtime_settings as mod

    monkeypatch.setattr(mod.postgres_store, "list_settings", fake_list)
    monkeypatch.setattr(mod.postgres_store, "save_setting", fake_save)
    monkeypatch.setattr(mod.postgres_store, "save_settings_audit", fake_audit)

    inst = RuntimeSettings()
    # reset any state carried by the singleton
    inst._overrides = {}
    inst._scheduler = None
    inst._store = store
    inst._audit = audit
    return inst


def test_spec_has_expected_keys():
    for key in (
        "TELEMETRY_POLL_INTERVAL_SEC",
        "ANOMALY_POLL_INTERVAL_SEC",
        "RING_BUFFER_RETENTION_SEC",
        "SNAPSHOT_BEFORE_SEC",
        "SNAPSHOT_AFTER_SEC",
        "DECISION_POLL_INTERVAL_SEC",
        "DECISION_WINDOW_SEC",
        "INCIDENT_RECOVERY_HOLD_SEC",
        "NOTIFY_ENABLED",
        "NOTIFY_RECIPIENT",
    ):
        assert key in SETTINGS_SPEC, f"{key} missing from SETTINGS_SPEC"


def test_coerce_int_range():
    rs = RuntimeSettings()
    assert rs._coerce("TELEMETRY_POLL_INTERVAL_SEC", "12") == 12
    with pytest.raises(ValueError):
        rs._coerce("TELEMETRY_POLL_INTERVAL_SEC", 0, strict=True)
    with pytest.raises(ValueError):
        rs._coerce("TELEMETRY_POLL_INTERVAL_SEC", 99999, strict=True)


def test_coerce_bool():
    rs = RuntimeSettings()
    assert rs._coerce("NOTIFY_ENABLED", "true") is True
    assert rs._coerce("NOTIFY_ENABLED", "0") is False
    assert rs._coerce("NOTIFY_ENABLED", True) is True
    with pytest.raises(ValueError):
        rs._coerce("NOTIFY_ENABLED", "banana", strict=True)


def test_coerce_email():
    rs = RuntimeSettings()
    with pytest.raises(ValueError):
        rs._coerce("NOTIFY_RECIPIENT", "not-an-email", strict=True)
    assert rs._coerce("NOTIFY_RECIPIENT", "a@b.com") == "a@b.com"


@pytest.mark.asyncio
async def test_update_persists_and_applies(rs):
    await rs.load()
    result = await rs.update({"TELEMETRY_POLL_INTERVAL_SEC": 15}, actor="tester")
    assert "TELEMETRY_POLL_INTERVAL_SEC" in result["changed"]
    assert rs._store["TELEMETRY_POLL_INTERVAL_SEC"] == 15
    assert any(a[0] == "TELEMETRY_POLL_INTERVAL_SEC" for a in rs._audit)


@pytest.mark.asyncio
async def test_update_rejects_premium_for_standard(rs):
    await rs.load()
    with pytest.raises(ValueError, match="premium"):
        await rs.update({"DECISION_WINDOW_SEC": 600}, actor="std", is_premium=False)
    # nothing persisted
    assert "DECISION_WINDOW_SEC" not in rs._store


@pytest.mark.asyncio
async def test_update_allows_premium_for_premium(rs):
    await rs.load()
    result = await rs.update({"DECISION_WINDOW_SEC": 600}, actor="owner", is_premium=True)
    assert "DECISION_WINDOW_SEC" in result["changed"]
    assert rs._store["DECISION_WINDOW_SEC"] == 600


@pytest.mark.asyncio
async def test_update_unknown_key_raises(rs):
    await rs.load()
    with pytest.raises(ValueError, match="unknown"):
        await rs.update({"NOPE": 1}, actor="tester")


@pytest.mark.asyncio
async def test_restart_required_for_non_live(rs):
    await rs.load()
    result = await rs.update({"INCIDENT_RECOVERY_HOLD_SEC": 45}, actor="owner")
    assert "INCIDENT_RECOVERY_HOLD_SEC" in result["requires_restart"]


class _FakeScheduler:
    def __init__(self):
        self.calls = []

    def add_job(self, fn, *a, **kw):
        self.calls.append((fn.__name__, kw.get("id")))


@pytest.mark.asyncio
async def test_live_interval_reschedules(rs, monkeypatch):
    sched = _FakeScheduler()
    rs.bind_scheduler(sched)

    import app.ingestion.telemetry_puller as tp
    monkeypatch.setattr(tp, "start_telemetry_puller", lambda s: s.add_job(tp.pull_once, id="telemetry_puller"))

    await rs.load()
    result = await rs.update({"TELEMETRY_POLL_INTERVAL_SEC": 20}, actor="tester")
    assert "TELEMETRY_POLL_INTERVAL_SEC" not in result["requires_restart"]
    assert ("pull_once", "telemetry_puller") in sched.calls
