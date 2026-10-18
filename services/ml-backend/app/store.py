"""
store.py — persistence for scored events and the model lifecycle (TimescaleDB, Doc3 Phase 1).

PgStore writes to the schema in infrastructure/local/init.sql (applied again here, idempotently,
so the backend also works against a fresh database). MemoryStore keeps the same data in bounded
in-process lists: the fallback when the database is unreachable, and what the tests use.

Writes are queued by the replay loop and flushed in batches once a second, so scoring never waits
on the database.
"""

import json
import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_SQL = (Path(__file__).resolve().parents[3] / "infrastructure" / "local" / "init.sql")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryStore:
    kind = "memory"

    def __init__(self, limit: int = 50000):
        self.metric_events: deque = deque(maxlen=limit)
        self.decisions: deque = deque(maxlen=5000)
        self.transitions: deque = deque(maxlen=5000)
        self.versions: dict[tuple[str, int], dict] = {}
        self.queries: dict[str, dict] = {}
        self.changes: deque = deque(maxlen=2000)

    async def start(self) -> bool:
        return True

    async def stop(self) -> None:
        pass

    async def write_metric_events(self, rows: list[dict]) -> None:
        self.metric_events.extend(rows)

    async def write_decision(self, d: dict) -> None:
        self.decisions.append({**d, "time": d.get("time") or _now()})

    async def write_transition(self, t: dict) -> None:
        self.transitions.append(t)

    async def write_version(self, v: dict) -> None:
        self.versions[(v["service_id"], v["version"])] = v

    async def write_query(self, q: dict) -> None:
        self.queries[q["query_id"]] = q

    async def write_change(self, c: dict) -> None:
        self.changes.append(c)

    async def recent_decisions(self, service_id: Optional[str], limit: int) -> list[dict]:
        rows = [d for d in self.decisions if service_id is None or d["service_id"] == service_id]
        return list(reversed(rows))[:limit]

    async def score_trend(self, minutes: int) -> list[dict]:
        buckets: dict[str, list[float]] = {}
        cutoff = _now().timestamp() - minutes * 60
        for r in self.metric_events:
            if r["time"].timestamp() >= cutoff:
                key = r["time"].replace(second=0, microsecond=0).isoformat()
                buckets.setdefault(key, []).append(r["anomaly_score"])
        return [{"bucket": k, "score": sum(v) / len(v)} for k, v in sorted(buckets.items())]

    async def counts(self) -> dict:
        return {"metric_events": len(self.metric_events), "decisions": len(self.decisions),
                "transitions": len(self.transitions), "queries": len(self.queries)}


class PgStore(MemoryStore):
    """TimescaleDB-backed store; inherits the in-memory views as a read cache for the live UI."""

    kind = "timescaledb"

    def __init__(self, dsn: str):
        super().__init__()
        self.dsn = dsn
        self.pool = None

    async def start(self) -> bool:
        import asyncpg

        try:
            self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=4, timeout=3)
            async with self.pool.acquire() as conn:
                await conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
            logger.info("store: TimescaleDB ready")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("store: database unavailable (%s), using in-memory store", exc)
            self.pool = None
            return False

    async def stop(self) -> None:
        if self.pool is not None:
            await self.pool.close()

    async def _exec_many(self, sql: str, args: list[tuple]) -> None:
        if self.pool is None or not args:
            return
        try:
            async with self.pool.acquire() as conn:
                await conn.executemany(sql, args)
        except Exception as exc:  # noqa: BLE001 - never let the DB break scoring
            logger.warning("store: write failed (%s)", exc)

    async def write_metric_events(self, rows: list[dict]) -> None:
        await super().write_metric_events(rows)
        await self._exec_many(
            "INSERT INTO metric_events (time, service_id, anomaly_score, severity, drift_detected,"
            " features, alarm, threshold, model_version, phase)"
            " VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10)",
            [(r["time"], r["service_id"], r["anomaly_score"], r["severity"], r["drift_detected"],
              json.dumps(r["features"]), r["alarm"], r["threshold"], r["model_version"], r["phase"])
             for r in rows])

    async def write_decision(self, d: dict) -> None:
        await super().write_decision(d)
        await self._exec_many(
            "INSERT INTO lifecycle_decisions (time, service_id, step, action, verdict, trigger,"
            " reason, evidence, query_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)",
            [(_now(), d["service_id"], d.get("step"), d.get("action"), d.get("verdict"),
              d.get("trigger"), d.get("reason"), json.dumps(d.get("evidence") or {}, default=str),
              d.get("query_id"))])

    async def write_transition(self, t: dict) -> None:
        await super().write_transition(t)
        await self._exec_many(
            "INSERT INTO lifecycle_transitions (service_id, seq, time, transition, from_version,"
            " to_version, reason, evidence) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)"
            " ON CONFLICT (service_id, seq) DO NOTHING",
            [(t["service_id"], t["seq"], _now(), t["transition"], t["from_version"],
              t["to_version"], t["reason"], json.dumps(t["evidence"], default=str))])

    async def write_version(self, v: dict) -> None:
        await super().write_version(v)
        await self._exec_many(
            "INSERT INTO model_versions (service_id, version, status, threshold, kind, verdict,"
            " reason, tags) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)"
            " ON CONFLICT (service_id, version) DO UPDATE SET status = EXCLUDED.status",
            [(v["service_id"], v["version"], v["status"], v["threshold"], v.get("kind"),
              v.get("verdict"), v.get("reason"), json.dumps(v.get("tags") or {}, default=str))])

    async def write_query(self, q: dict) -> None:
        await super().write_query(q)
        await self._exec_many(
            "INSERT INTO operator_queries (query_id, service_id, status, answer, operator,"
            " answered_at, reason, evidence) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)"
            " ON CONFLICT (query_id) DO UPDATE SET status = EXCLUDED.status,"
            " answer = EXCLUDED.answer, operator = EXCLUDED.operator,"
            " answered_at = EXCLUDED.answered_at",
            [(q["query_id"], q["service_id"], q["status"], q.get("answer"), q.get("operator"),
              _now() if q["status"] == "answered" else None, q.get("reason"),
              json.dumps(q.get("evidence") or {}, default=str))])

    async def write_change(self, c: dict) -> None:
        await super().write_change(c)
        await self._exec_many(
            "INSERT INTO change_events (time, service_id, kind, detail) VALUES ($1,$2,$3,$4::jsonb)",
            [(_now(), c["service_id"], c["kind"], json.dumps(c.get("detail") or {}, default=str))])

    async def score_trend(self, minutes: int) -> list[dict]:
        if self.pool is None:
            return await super().score_trend(minutes)
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT time_bucket('1 minute', time) AS bucket, avg(anomaly_score) AS score"
                    " FROM metric_events WHERE time > now() - make_interval(mins => $1)"
                    " GROUP BY bucket ORDER BY bucket", minutes)
            return [{"bucket": r["bucket"].isoformat(), "score": float(r["score"])} for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("store: trend query failed (%s)", exc)
            return await super().score_trend(minutes)

    async def counts(self) -> dict:
        if self.pool is None:
            return await super().counts()
        try:
            async with self.pool.acquire() as conn:
                out = {}
                for table in ("metric_events", "lifecycle_decisions", "lifecycle_transitions",
                              "operator_queries", "model_versions"):
                    out[table] = await conn.fetchval(f"SELECT count(*) FROM {table}")
                return out
        except Exception:  # noqa: BLE001
            return await super().counts()


async def make_store(dsn: Optional[str]) -> MemoryStore:
    if dsn:
        store = PgStore(dsn)
        if await store.start():
            return store
    return MemoryStore()
