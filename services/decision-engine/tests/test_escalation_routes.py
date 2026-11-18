# services/decision-engine/tests/test_escalation_routes.py
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import escalations as esc_routes


class FakeStore:
    def __init__(self):
        self.rows = {
            "ESC-1": {
                "id": "ESC-1", "decision_id": "DEC-1",
                "anomaly_id": "ANM-1", "service_id": "auth-service",
                "status": "PENDING", "attempt": 0, "max_attempts": 3,
                "notifications": [], "response": None, "failure_report": None,
                "next_attempt_at": None,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
        }

    async def get_escalation(self, eid):
        return self.rows.get(eid)

    async def save_escalation(self, payload):
        self.rows[payload["id"]] = dict(payload)
        return True

    async def list_escalations(self, statuses=None, limit=100):
        return list(self.rows.values())[:limit]

    async def list_escalations_due(self, now=None):
        return []


@pytest.fixture
def client(monkeypatch):
    import app.persistence.postgres as pg
    monkeypatch.setattr(pg, "postgres_store", FakeStore())
    app = FastAPI()
    app.include_router(esc_routes.router)
    return TestClient(app)


def test_list(client):
    r = client.get("/api/decisions/escalations")
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_get_one(client):
    r = client.get("/api/decisions/escalations/ESC-1")
    assert r.status_code == 200
    assert r.json()["id"] == "ESC-1"


def test_get_missing(client):
    r = client.get("/api/decisions/escalations/NOPE")
    assert r.status_code == 404


def test_ack_approved(client):
    r = client.post("/api/decisions/escalations/ESC-1/ack?decision=APPROVED&actor=ops")
    assert r.status_code == 200
    assert r.json()["escalation"]["status"] == "RESOLVED"
    assert r.json()["escalation"]["response"]["decision"] == "APPROVED"


def test_ack_rejected(client):
    r = client.post("/api/decisions/escalations/ESC-1/ack?decision=REJECTED")
    assert r.status_code == 200
    assert r.json()["escalation"]["response"]["decision"] == "REJECTED"