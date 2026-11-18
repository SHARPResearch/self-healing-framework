# services/decision-engine/tests/test_shadow_routes.py
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import shadow as shadow_routes


class FakeStore:
    def __init__(self):
        self.shadows = {
        "SHD-1": {
            "id": "SHD-1", "decision_id": "DEC-1", "anomaly_id": "ANM-1",
            "service_id": "auth-service", "candidate_action": "RESTART_POD",
            "confidence": 0.71, "risk": "MEDIUM",
            "simulated_outcome": {
                "EXPECTED_ANOMALY_DROP": 0.34,
                "EXPECTED_RECOVERY_TIME_SEC": 45,
            },
            "actual_outcome": None,
            "verdict": None, "learning": None,
            "observed_at": None, "resolved_at": None,
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    }

    async def list_shadows(self, limit=100, verdict=None, service_id=None):
        out = list(self.shadows.values())
        if verdict:
            out = [r for r in out if r["verdict"] == verdict]
        if service_id:
            out = [r for r in out if r["service_id"] == service_id]
        return out[:limit]

    async def get_shadow(self, sid):
        return self.shadows.get(sid)

    async def update_shadow_outcome(self, shadow_id, **kw):
        r = self.shadows.get(shadow_id)
        if not r:
            return False
        r["verdict"] = kw["verdict"]
        r["actual_outcome"] = kw["actual_outcome"]
        r["learning"] = kw["learning"]
        r["observed_at"] = kw["observed_at"]
        r["resolved_at"] = kw["resolved_at"]
        return True

    async def shadow_metrics(self):
        return {
            "total_shadows": 1, "open": 1,
            "resolved_naturally": 0, "would_have_helped": 0,
            "unnecessary": 0, "unknown": 0, "still_active": 0,
            "unnecessary_action_rate": 0.0,
            "mean_resolution_time_sec": 0.0,
        }


@pytest.fixture
def client(monkeypatch):
    import app.persistence.postgres as pg
    import app.decision.shadow_observer as so
    fake = FakeStore()
    monkeypatch.setattr(pg, "postgres_store", fake)
    monkeypatch.setattr(so, "postgres_store", fake)

    app = FastAPI()
    app.include_router(shadow_routes.router)
    return TestClient(app)


def test_list_shadows(client):
    r = client.get("/api/decisions/shadow")
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_get_missing(client):
    r = client.get("/api/decisions/shadow/NOPE")
    assert r.status_code == 404


def test_metrics(client):
    r = client.get("/api/decisions/shadow/metrics")
    assert r.status_code == 200
    assert "unnecessary_action_rate" in r.json()


def test_manual_resolve(client):
    r = client.post(
        "/api/decisions/shadow/SHD-1/resolve?resolved_naturally=true&resolution_time_sec=50"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["shadow"]["verdict"] == "ACTION_WOULD_HAVE_BEEN_UNNECESSARY"