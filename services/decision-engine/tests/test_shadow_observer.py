# services/decision-engine/tests/test_shadow_observer.py
"""
Tests for app.decision.shadow_observer._classify_outcome + observe_once.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.decision import shadow_observer
from app.decision.shadow_observer import _classify_outcome, observe_once


# ─────────────────────────────────────────────────────────────────────
# Fake store
# ─────────────────────────────────────────────────────────────────────
class FakeStore:
    def __init__(self):
        self.shadows: dict[str, dict] = {}
        self.escalations: dict[str, dict] = {}
        self.anomalies: dict[str, dict] = {}
        self.incidents: dict[str, dict] = {}

    async def list_open_shadows(self, min_age_sec=300, limit=200):
        now = datetime.now(timezone.utc)
        out = []
        for r in self.shadows.values():
            if r.get("verdict") is not None:
                continue
            created = r.get("created_at")
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (now - created).total_seconds() < min_age_sec:
                continue
            out.append(r)
        return out[:limit]

    async def get_shadow(self, sid):
        return self.shadows.get(sid)

    async def update_shadow_outcome(self, shadow_id, **kw):
        r = self.shadows.get(shadow_id)
        if not r or r.get("verdict") is not None:
            return False
        r["verdict"] = kw["verdict"]
        r["actual_outcome"] = kw["actual_outcome"]
        r["learning"] = kw["learning"]
        r["observed_at"] = kw["observed_at"]
        r["resolved_at"] = kw["resolved_at"]
        return True

    async def mark_shadow_abandoned(self, *, shadow_id, reason, observed_at):
        r = self.shadows.get(shadow_id)
        if r and r.get("verdict") is None:
            r["verdict"] = reason
            r["observed_at"] = observed_at
        return True

    async def get_escalation_by_decision(self, decision_id):
        for e in self.escalations.values():
            if e["decision_id"] == decision_id:
                return e
        return None

    async def get_anomaly(self, aid):
        return self.anomalies.get(aid)

    async def get_incident_state(self, sid):
        return self.incidents.get(sid)


@pytest.fixture
def fake_pg(monkeypatch):
    import app.persistence.postgres as pg
    fake = FakeStore()
    monkeypatch.setattr(pg, "postgres_store", fake)
    # Also patch the module-level reference inside shadow_observer
    monkeypatch.setattr(shadow_observer, "postgres_store", fake)
    return fake


def _shadow_row(shadow_id="SHD-1", age_sec=400) -> dict:
    return {
        "id": shadow_id,
        "decision_id": "DEC-1",
        "anomaly_id": "ANM-1",
        "service_id": "auth-service",
        "candidate_action": "RESTART_POD",
        "confidence": 0.71,
        "risk": "MEDIUM",
        "simulated_outcome": {"EXPECTED_ANOMALY_DROP": 0.34, "EXPECTED_RECOVERY_TIME_SEC": 45},
        "actual_outcome": None,
        "verdict": None,
        "learning": None,
        "created_at": datetime.now(timezone.utc) - timedelta(seconds=age_sec),
    }


# ─────────────────────────────────────────────────────────────────────
# Classification
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_classify_naturally_resolved(fake_pg):
    row = _shadow_row()
    fake_pg.shadows[row["id"]] = row
    fake_pg.anomalies["ANM-1"] = {"id": "ANM-1", "snapshot_status": "captured",
                                   "captured_at": datetime.now(timezone.utc)}
    fake_pg.incidents["auth-service"] = {"current_health": "healthy", "incident_start": None}

    out = await _classify_outcome(row)
    assert out is not None
    assert out["resolved_naturally"] is True
    assert out["resolution_path"] == "NATURAL"


@pytest.mark.asyncio
async def test_classify_escalation_approved(fake_pg):
    row = _shadow_row()
    fake_pg.shadows[row["id"]] = row
    fake_pg.escalations["ESC-1"] = {
        "id": "ESC-1", "decision_id": "DEC-1", "status": "RESOLVED",
        "response": {"decision": "APPROVED",
                      "at": datetime.now(timezone.utc).isoformat()},
    }
    out = await _classify_outcome(row)
    assert out is not None
    assert out["resolved_naturally"] is False
    assert out["resolution_path"] == "ESCALATION_APPROVED"


@pytest.mark.asyncio
async def test_classify_escalation_pending_skips(fake_pg):
    row = _shadow_row()
    fake_pg.shadows[row["id"]] = row
    fake_pg.escalations["ESC-1"] = {
        "id": "ESC-1", "decision_id": "DEC-1", "status": "AWAITING_HUMAN", "response": None,
    }
    out = await _classify_outcome(row)
    assert out is None   # not ready yet


@pytest.mark.asyncio
async def test_classify_still_active_past_max_wait(fake_pg, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "SHADOW_MAX_WAIT_MIN", 5)

    row = _shadow_row(age_sec=600)   # 10 min old, max wait 5 min
    fake_pg.shadows[row["id"]] = row
    fake_pg.anomalies["ANM-1"] = {"id": "ANM-1", "snapshot_status": "pending"}
    fake_pg.incidents["auth-service"] = {"current_health": "degraded", "incident_start": datetime.now(timezone.utc)}

    out = await _classify_outcome(row)
    assert out is not None
    assert out.get("terminal") is True
    assert out["resolution_path"] == "STILL_ACTIVE"


# ─────────────────────────────────────────────────────────────────────
# observe_once — end-to-end single cycle
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_observe_once_fills_natural_verdict(fake_pg):
    row = _shadow_row(age_sec=400)
    fake_pg.shadows[row["id"]] = row

    # Resolution took 50s (well within expected 45s * 1.5 = 67.5s).
    # `created_at` in the row is `now - 400s`, so `captured_at` must be
    # created_at + 50s for `_seconds_between` to yield 50.
    created_at = row["created_at"]
    captured_at = created_at + timedelta(seconds=50)

    fake_pg.anomalies["ANM-1"] = {
        "id": "ANM-1", "snapshot_status": "captured",
        "captured_at": captured_at,
    }
    fake_pg.incidents["auth-service"] = {
        "current_health": "healthy", "incident_start": None,
    }

    n = await observe_once()
    assert n == 1
    assert row["verdict"] == "ACTION_WOULD_HAVE_BEEN_UNNECESSARY"
    assert row["actual_outcome"]["ANOMALY_RESOLVED_NATURALLY"] is True
    assert row["actual_outcome"]["RESOLUTION_TIME_SEC"] == 50
    
@pytest.mark.asyncio
async def test_observe_once_marks_helped_when_slow(fake_pg):
    """A slow natural resolution (> 1.5x expected) → HELPED, not UNNECESSARY."""
    row = _shadow_row(age_sec=400)
    fake_pg.shadows[row["id"]] = row

    # Resolution took 200s — way beyond 45s * 1.5 = 67.5s.
    created_at = row["created_at"]
    captured_at = created_at + timedelta(seconds=200)
    fake_pg.anomalies["ANM-1"] = {
        "id": "ANM-1", "snapshot_status": "captured",
        "captured_at": captured_at,
    }
    fake_pg.incidents["auth-service"] = {
        "current_health": "healthy", "incident_start": None,
    }

    n = await observe_once()
    assert n == 1
    assert row["verdict"] == "ACTION_WOULD_HAVE_HELPED"
    
@pytest.mark.asyncio
async def test_observe_once_skips_young_shadows(fake_pg):
    row = _shadow_row(age_sec=30)   # too young
    fake_pg.shadows[row["id"]] = row
    n = await observe_once()
    assert n == 0
    assert row["verdict"] is None