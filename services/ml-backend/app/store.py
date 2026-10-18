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


def parse_log_filter(text: str) -> dict:
    """
    The Logs page filter box, Railway style: free text plus `service:`, `level:` and `source:`
    terms, e.g. `checkpoint service:timescaledb level:error`. Repeated keys match any of the values.
    """
    out: dict = {"text": [], "service": [], "level": [], "source": []}
    for token in text.split():
        key, sep, value = token.partition(":")
        if sep and value and key.lower().lstrip("@") in ("service", "level", "source"):
            out[key.lower().lstrip("@")].append(value.lower())
        else:
            out["text"].append(token)
    return out


def _bucket_seconds(start: datetime, end: datetime, buckets: int = 60) -> int:
    span = max((end - start).total_seconds(), 1.0)
    return max(1, int(round(span / buckets)))


class MemoryStore:
    kind = "memory"

    def __init__(self, limit: int = 50000):
        self.metric_events: deque = deque(maxlen=limit)
        self.decisions: deque = deque(maxlen=5000)
        self.transitions: deque = deque(maxlen=5000)
        self.versions: dict[tuple[str, int], dict] = {}
        self.queries: dict[str, dict] = {}
        self.changes: deque = deque(maxlen=2000)
        self.logs: deque = deque(maxlen=20000)
        self._log_ids: set[str] = set()

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

    # -- logs ------------------------------------------------------------------------------------
    async def write_logs(self, lines: list[dict]) -> None:
        for line in lines:
            if line["id"] in self._log_ids:
                continue
            if len(self.logs) == self.logs.maxlen:
                self._log_ids.discard(self.logs[0]["id"])
            self.logs.append(line)
            self._log_ids.add(line["id"])

    async def clear_logs(self, source: str) -> None:
        """Forget one source's lines (a demo reset drops the old fleet's lifecycle lines)."""
        keep = [ln for ln in self.logs if ln["source"] != source]
        self.logs.clear()
        self.logs.extend(keep)
        self._log_ids = {ln["id"] for ln in keep}

    @staticmethod
    def _log_matches(line: dict, f: dict) -> bool:
        names = {line["service"].lower(), (line.get("service_id") or "").lower()}
        if f["service"] and not names & set(f["service"]):
            return False
        if f["level"] and line["level"] not in f["level"]:
            return False
        if f["source"] and line["source"] not in f["source"]:
            return False
        hay = f"{line['message']} {line['service']}".lower()
        return all(t.lower() in hay for t in f["text"])

    async def query_logs(self, q: str = "", since: Optional[datetime] = None,
                         until: Optional[datetime] = None, before: Optional[datetime] = None,
                         limit: int = 500) -> list[dict]:
        """Newest `limit` matching lines, returned oldest first (the order the page shows them)."""
        f = parse_log_filter(q)
        rows = [ln for ln in self.logs
                if (since is None or ln["time"] >= since) and (until is None or ln["time"] <= until)
                and (before is None or ln["time"] < before) and self._log_matches(ln, f)]
        rows.sort(key=lambda ln: (ln["time"], ln["id"]))
        return rows[-limit:]

    async def log_histogram(self, q: str, since: datetime, until: datetime) -> dict:
        f = parse_log_filter(q)
        width = _bucket_seconds(since, until)
        buckets: dict[int, dict] = {}
        for ln in self.logs:
            if since <= ln["time"] <= until and self._log_matches(ln, f):
                key = int(ln["time"].timestamp() // width * width)
                b = buckets.setdefault(key, {"info": 0, "warn": 0, "error": 0})
                b[ln["level"] if ln["level"] in ("warn", "error") else "info"] += 1
        return {"bucketSeconds": width, "buckets": [
            {"time": datetime.fromtimestamp(k, timezone.utc).isoformat(), **v}
            for k, v in sorted(buckets.items())]}

    async def log_services(self) -> list[dict]:
        counts: dict[str, dict] = {}
        for ln in self.logs:
            c = counts.setdefault(ln["service"], {"service": ln["service"], "source": ln["source"], "count": 0})
            c["count"] += 1
        return sorted(counts.values(), key=lambda c: c["service"])

    async def latest_log_times(self) -> dict[str, datetime]:
        out: dict[str, datetime] = {}
        floor = datetime.min.replace(tzinfo=timezone.utc)
        for ln in self.logs:
            if ln["time"] > out.get(ln["service"], floor):
                out[ln["service"]] = ln["time"]
        return out

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

    # -- logs ------------------------------------------------------------------------------------
    @staticmethod
    def _log_where(f: dict, args: list, since=None, until=None, before=None) -> str:
        clauses: list[str] = []

        def add(sql: str, *values) -> None:
            base = len(args)
            args.extend(values)
            clauses.append(sql.format(*[f"${base + i + 1}" for i in range(len(values))]))

        if since is not None:
            add("time >= {}", since)
        if until is not None:
            add("time <= {}", until)
        if before is not None:
            add("time < {}", before)
        if f["service"]:
            add("(lower(service) = ANY({}) OR lower(coalesce(service_id, '')) = ANY({}))",
                f["service"], f["service"])
        if f["level"]:
            add("level = ANY({})", f["level"])
        if f["source"]:
            add("source = ANY({})", f["source"])
        for t in f["text"]:
            add("(message ILIKE {} OR service ILIKE {})", f"%{t}%", f"%{t}%")
        return (" WHERE " + " AND ".join(clauses)) if clauses else ""

    async def write_logs(self, lines: list[dict]) -> None:
        await super().write_logs(lines)
        if self.pool is None or not lines:
            return
        try:                                  # debug only: a warning here would itself be a log line
            async with self.pool.acquire() as conn:
                await conn.executemany(
                    "INSERT INTO service_logs (time, id, service, service_id, source, level, message,"
                    " attrs) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb) ON CONFLICT DO NOTHING",
                    [(ln["time"], ln["id"], ln["service"], ln.get("service_id"), ln["source"],
                      ln["level"], ln["message"], json.dumps(ln.get("attrs") or {}, default=str))
                     for ln in lines])
        except Exception as exc:  # noqa: BLE001
            logger.debug("store: log write failed (%s)", exc)

    async def clear_logs(self, source: str) -> None:
        await super().clear_logs(source)
        if self.pool is None:
            return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("DELETE FROM service_logs WHERE source = $1", source)
        except Exception as exc:  # noqa: BLE001
            logger.debug("store: clearing logs failed (%s)", exc)

    @staticmethod
    def _row_to_log(r) -> dict:
        attrs = r["attrs"]
        return {"id": r["id"], "time": r["time"], "service": r["service"], "service_id": r["service_id"],
                "source": r["source"], "level": r["level"], "message": r["message"],
                "attrs": json.loads(attrs) if isinstance(attrs, str) else (attrs or {})}

    async def query_logs(self, q: str = "", since=None, until=None, before=None, limit: int = 500) -> list[dict]:
        if self.pool is None:
            return await super().query_logs(q, since, until, before, limit)
        args: list = []
        where = self._log_where(parse_log_filter(q), args, since, until, before)
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    f"SELECT * FROM (SELECT * FROM service_logs{where} ORDER BY time DESC, id DESC"
                    f" LIMIT {int(limit)}) t ORDER BY time, id", *args)
            return [self._row_to_log(r) for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("store: log query failed (%s)", exc)
            return await super().query_logs(q, since, until, before, limit)

    async def log_histogram(self, q: str, since, until) -> dict:
        if self.pool is None:
            return await super().log_histogram(q, since, until)
        width = _bucket_seconds(since, until)
        args: list = [float(width)]
        where = self._log_where(parse_log_filter(q), args, since, until)
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT to_timestamp(floor(extract(epoch FROM time) / $1) * $1) AS bucket,"
                    " count(*) FILTER (WHERE level = 'error') AS error,"
                    " count(*) FILTER (WHERE level = 'warn') AS warn,"
                    " count(*) FILTER (WHERE level NOT IN ('warn', 'error')) AS info"
                    f" FROM service_logs{where} GROUP BY bucket ORDER BY bucket", *args)
            return {"bucketSeconds": width, "buckets": [
                {"time": r["bucket"].isoformat(), "info": r["info"], "warn": r["warn"],
                 "error": r["error"]} for r in rows]}
        except Exception as exc:  # noqa: BLE001
            logger.warning("store: log histogram failed (%s)", exc)
            return await super().log_histogram(q, since, until)

    async def log_services(self) -> list[dict]:
        if self.pool is None:
            return await super().log_services()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT service, min(source) AS source, count(*) AS count FROM service_logs"
                    " GROUP BY service ORDER BY service")
            return [{"service": r["service"], "source": r["source"], "count": r["count"]} for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("store: log services failed (%s)", exc)
            return await super().log_services()

    async def latest_log_times(self) -> dict:
        if self.pool is None:
            return await super().latest_log_times()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT service, max(time) AS t FROM service_logs GROUP BY service")
            return {r["service"]: r["t"] for r in rows}
        except Exception:  # noqa: BLE001
            return await super().latest_log_times()

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
                              "operator_queries", "model_versions", "service_logs"):
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
