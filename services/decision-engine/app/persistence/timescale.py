"""
Async pool for telemetry (Tiger Cloud TimescaleDB).
"""
import asyncpg
import json
import logging
from typing import Optional
from app.config import settings

log = logging.getLogger(__name__)


class TimescaleStore:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        dsn = settings.TELEMETRY_DB_URL
        if "sslmode=require" not in dsn:
            sep = "&" if "?" in dsn else "?"
            dsn = f"{dsn}{sep}sslmode=require"

        self.pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
        log.info("Connected to Tiger Cloud (telemetry_db)")

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def ensure_schema(self, ddl: str):
        async with self.pool.acquire() as conn:
            for stmt in _split_sql(ddl):
                stmt = stmt.strip()
                if not stmt:
                    continue
                # create_hypertable() is a SELECT — must use fetch, not execute
                if stmt.upper().lstrip().startswith("SELECT"):
                    await conn.fetch(stmt)
                else:
                    await conn.execute(stmt)

    # ── Infra snapshots ────────────────────────────────────────
    async def insert_infra_snapshot(self, anomaly_id, time_, service_id, payload):
        sql = """
            INSERT INTO infra_snapshots (
                anomaly_id, time, service_id,
                service_name, layer, team, runtime, version, region,
                node_pool, node, container_image, uptime_seconds,
                pod_count, ready_pods, restarts_last_5m,
                cpu_usage_pct, cpu_cores_used, cpu_throttled_pct,
                mem_used_mb, mem_limit_mb, mem_pct, mem_oom_kills,
                net_rx_kbps, net_tx_kbps,
                disk_read_iops, disk_write_iops, disk_used_pct,
                gc_pause_p95_ms, gc_collections,
                raw
                ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
                $21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31
            )
            ON CONFLICT (anomaly_id, time) DO NOTHING
        """
        cpu = payload.get("cpu") or {}
        mem = payload.get("memory") or {}
        net = payload.get("network") or {}
        disk = payload.get("disk") or {}
        gc = payload.get("gc") or {}

        async with self.pool.acquire() as conn:
            await conn.execute(
                sql,
                anomaly_id, time_, service_id,
                payload.get("service_name"), payload.get("layer"), payload.get("team"),
                payload.get("runtime"), payload.get("version"), payload.get("region"),
                payload.get("node_pool"), payload.get("node"),
                payload.get("container_image"), payload.get("uptime_seconds"),
                payload.get("pod_count"), payload.get("ready_pods"),
                payload.get("restarts_last_5m"),
                cpu.get("usage_pct"), cpu.get("cores_used"), cpu.get("throttled_pct"),
                mem.get("used_mb"), mem.get("limit_mb"),
                mem.get("pct"), mem.get("oom_kills"),
                net.get("rx_kbps"), net.get("tx_kbps"),
                disk.get("read_iops"), disk.get("write_iops"), disk.get("used_pct"),
                gc.get("pause_p95_ms"), gc.get("collections_per_min"),
                json.dumps(payload),
            )

    async def insert_app_snapshot(self, anomaly_id, time_, service_id, payload):
        sql = """
            INSERT INTO app_snapshots (
                anomaly_id, time, service_id,
                service_name, layer, team,
                rps, throughput_bps,
                latency_p50, latency_p90, latency_p95, latency_p99,
                latency_p999, latency_max,
                error_rate, error_budget_pct,
                status_2xx, status_3xx, status_4xx, status_5xx,
                active_conns, queue_depth, queue_lag_ms,
                db_p95_ms, db_pool_used, db_pool_max,
                cache_hit_rate, cache_evictions,
                saturation_pct,
                raw
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
                $21,$22,$23,$24,$25,$26,$27,$28,$29,$30
            )
            ON CONFLICT (anomaly_id, time) DO NOTHING
        """
        lat = payload.get("latency_ms") or {}
        sc = payload.get("status_codes") or {}

        async with self.pool.acquire() as conn:
            await conn.execute(
                sql,
                anomaly_id, time_, service_id,
                payload.get("service_name"), payload.get("layer"), payload.get("team"),
                payload.get("requests_per_sec"), payload.get("throughput_bytes_per_sec"),
                lat.get("p50"), lat.get("p90"), lat.get("p95"), lat.get("p99"),
                lat.get("p999"), lat.get("max"),
                payload.get("error_rate"), payload.get("error_budget_remaining_pct"),
                sc.get("2xx"), sc.get("3xx"), sc.get("4xx"), sc.get("5xx"),
                payload.get("active_connections"),
                payload.get("queue_depth"), payload.get("queue_lag_ms"),
                payload.get("db_query_p95_ms"),
                payload.get("db_connection_pool_used"),
                payload.get("db_connection_pool_max"),
                payload.get("cache_hit_rate"),
                payload.get("cache_evictions_per_min"),
                payload.get("saturation_pct"),
                json.dumps(payload),
            )

    async def get_infra_snapshots(self, anomaly_id: str) -> list[dict]:
        sql = "SELECT * FROM infra_snapshots WHERE anomaly_id = $1 ORDER BY time ASC"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, anomaly_id)
            return [dict(r) for r in rows]

    async def get_app_snapshots(self, anomaly_id: str) -> list[dict]:
        sql = "SELECT * FROM app_snapshots WHERE anomaly_id = $1 ORDER BY time ASC"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, anomaly_id)
            return [dict(r) for r in rows]

    async def get_service_history(self, service_id: str, limit: int = 100) -> dict:
        infra_sql = """
        SELECT time, cpu_usage_pct, mem_pct, ready_pods, pod_count, restarts_last_5m
        FROM infra_snapshots WHERE service_id = $1
        ORDER BY time DESC LIMIT $2
        """
        app_sql = """
        SELECT time, rps, latency_p50, latency_p95, latency_p99, error_rate
        FROM app_snapshots WHERE service_id = $1
        ORDER BY time DESC LIMIT $2
        """
        async with self.pool.acquire() as conn:
            infra = await conn.fetch(infra_sql, service_id, limit)
            app = await conn.fetch(app_sql, service_id, limit)
            return {
                "service_id": service_id,
                "infra": [dict(r) for r in reversed(infra)],
                "app": [dict(r) for r in reversed(app)],
            }


def _split_sql(script: str) -> list[str]:
    """Split a SQL script into statements on ';' boundaries."""
    statements = []
    buf = []
    for line in script.splitlines():
        stripped = line.strip()
        # Skip pure comments and blank lines
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buf).rstrip(";").strip())
            buf = []
    if buf:
        statements.append("\n".join(buf).strip())
    return statements


timescale_store = TimescaleStore()