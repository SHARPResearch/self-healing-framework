# services/decision-engine/tests/test_escalation_queue.py
from __future__ import annotations

import pytest

from app.decision.escalation import queue as esc_queue
from app.decision.escalation.queue import EscalationStatus


class FakeStore:
    def __init__(self):
        self.rows: dict[str, dict] = {}

    async def save_escalation(self, payload):
        self.rows[payload["id"]] = dict(payload)
        return True

    async def get_escalation(self, eid):
        return self.rows.get(eid)

    async def list_escalations(self, statuses=None, limit=100):
        out = list(self.rows.values())
        if statuses:
            out = [r for r in out if r["status"] in statuses]
        return out[:limit]

    async def list_escalations_due(self, now=None):
        return [
            r for r in self.rows.values()
            if r.get("next_attempt_at") and r["status"] in ("PENDING", "AWAITING_HUMAN")
        ]


@pytest.fixture
def fake_pg(monkeypatch):
    import app.persistence.postgres as pg
    fake = FakeStore()
    monkeypatch.setattr(pg, "postgres_store", fake)
    yield fake


@pytest.mark.asyncio
async def test_enqueue_creates_pending(fake_pg):
    esc = await esc_queue.enqueue("DEC-1", "ANM-1", "auth-service")
    assert esc.status == EscalationStatus.PENDING
    assert esc.attempt == 0
    assert esc.id in fake_pg.rows


@pytest.mark.asyncio
async def test_ack_resolves(fake_pg):
    esc = await esc_queue.enqueue("DEC-1", "ANM-1", "auth-service")
    updated = await esc_queue.ack(esc.id, actor="ops@example.com", decision="APPROVED")
    assert updated is not None
    assert updated.status == EscalationStatus.RESOLVED
    assert updated.response["decision"] == "APPROVED"


@pytest.mark.asyncio
async def test_ack_terminal_is_noop(fake_pg):
    esc = await esc_queue.enqueue("DEC-1", "ANM-1", "auth-service")
    await esc_queue.ack(esc.id)
    second = await esc_queue.ack(esc.id, decision="REJECTED")
    assert second.status == EscalationStatus.RESOLVED  # unchanged


@pytest.mark.asyncio
async def test_record_attempt_advances_state(fake_pg):
    esc = await esc_queue.enqueue("DEC-1", "ANM-1", "auth-service")
    await esc_queue.record_attempt(esc, subject="s1", body="b1", sent=True)
    assert esc.attempt == 1
    assert esc.status == EscalationStatus.AWAITING_HUMAN
    assert esc.next_attempt_at is not None


@pytest.mark.asyncio
async def test_record_attempt_terminates_after_three(fake_pg):
    esc = await esc_queue.enqueue("DEC-1", "ANM-1", "auth-service")
    await esc_queue.record_attempt(esc, subject="s1", body="b1", sent=True)
    await esc_queue.record_attempt(esc, subject="s2", body="b2", sent=True)
    await esc_queue.record_attempt(esc, subject="s3", body="b3", sent=True)
    assert esc.attempt == 3
    assert esc.status == EscalationStatus.MANUAL_REQUIRED
    assert esc.next_attempt_at is None
    assert "Manual intervention required" in esc.failure_report