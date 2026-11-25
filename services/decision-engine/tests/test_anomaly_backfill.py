import pytest

from app.persistence.postgres import PostgresStore


class FakeConnection:
    def __init__(self):
        self.sql = ""
        self.args = ()

    async def fetch(self, sql, *args):
        self.sql = sql
        self.args = args
        return []


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return FakeAcquire(self.connection)


@pytest.mark.asyncio
async def test_backfill_has_no_age_cap_when_disabled():
    store = PostgresStore()
    connection = FakeConnection()
    store.pool = FakePool(connection)

    rows = await store.get_anomalies_without_decisions(
        window_sec=300,
        limit=100,
        backfill_max_age_sec=None,
    )

    assert rows == []
    assert "NOW()" not in connection.sql
    assert "ORDER BY a.detected_at DESC" in connection.sql
    assert connection.args == (100,)


@pytest.mark.asyncio
async def test_backfill_keeps_age_cap_when_configured():
    store = PostgresStore()
    connection = FakeConnection()
    store.pool = FakePool(connection)

    await store.get_anomalies_without_decisions(
        window_sec=300,
        limit=100,
        backfill_max_age_sec=86400,
    )

    assert "NOW() - INTERVAL '1 second' * $1" in connection.sql
    assert connection.args == (86400, 100)
