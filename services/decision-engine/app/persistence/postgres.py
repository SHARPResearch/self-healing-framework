"""
Async pool for the anomaly events DB (Neon Postgres).
"""
import asyncpg
import json
import logging
from typing import Optional
from app.config import settings

log = logging.getLogger(__name__)


class PostgresStore:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        # Neon requires SSL. asyncpg accepts sslmode via the DSN query param,
        # but pooler URLs may strip it — set explicitly.
        dsn = settings.ANOMALY_DB_URL
        if "sslmode=require" not in dsn:
            sep = "&" if "?" in dsn else "?"
            dsn = f"{dsn}{sep}sslmode=require"

        self.pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
        log.info("Connected to Neon (anomaly_db)")

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def ensure_schema(self, ddl: str):
        async with self.pool.acquire() as conn:
            await conn.execute(ddl)

    async def save_anomaly(self, a: dict) -> bool:
        sql = """
        INSERT INTO anomaly_events (
            id, service_id, service_name, team, layer,
            anomaly_score, severity, metric, actual_value, expected_value,
            deviation_sigma, confidence, model_version, features, detected_at
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15
        )
        ON CONFLICT (id) DO NOTHING
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                sql,
                a["id"], a["service_id"],
                a.get("service_name"), a.get("team"), a.get("layer"),
                a["anomaly_score"], a["severity"],
                a.get("metric"), a.get("actual_value"), a.get("expected_value"),
                a.get("deviation_sigma"), a.get("confidence"), a.get("model_version"),
                json.dumps(a.get("features", {})),
                a["detected_at"],
            )
            return result == "INSERT 0 1"

    async def list_recent_anomalies(self, limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM anomaly_events ORDER BY detected_at DESC LIMIT $1"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, limit)
            return [dict(r) for r in rows]

    async def get_anomaly(self, anomaly_id: str) -> Optional[dict]:
        sql = "SELECT * FROM anomaly_events WHERE id = $1"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql, anomaly_id)
            return dict(row) if row else None

    async def pending_snapshots_due(self) -> list[dict]:
        sql = """
        SELECT * FROM anomaly_events
        WHERE snapshot_status = 'pending'
          AND detected_at + INTERVAL '1 second' * $1 <= NOW()
        ORDER BY detected_at ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, settings.SNAPSHOT_AFTER_SEC)
            return [dict(r) for r in rows]

    async def mark_snapshot_captured(self, anomaly_id, window_from, window_to):
        sql = """
        UPDATE anomaly_events
        SET snapshot_status = 'captured',
            snapshot_from = $2,
            snapshot_to   = $3,
            captured_at   = NOW()
        WHERE id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, anomaly_id, window_from, window_to)

    async def mark_snapshot_failed(self, anomaly_id):
        sql = "UPDATE anomaly_events SET snapshot_status='failed' WHERE id=$1"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, anomaly_id)

        # ── DECISION LOG ────────────────────────────────────────────
    
    async def save_decision(self, row: dict) -> bool:
        """
        Insert one decision_log row. Returns True if inserted, False if
        the id already exists (idempotent).
        """
        import json

        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO decision_log (
                        id, anomaly_id, service_id, rule_id, rule_version,
                        action, action_params,
                        detection_conf, rule_conf, final_conf,
                        base_risk, blast_factor, centrality, effective_severity,
                        policy_outcome, policy_reason,
                        context
                    ) VALUES (
                        $1,$2,$3,$4,$5,
                        $6,$7,
                        $8,$9,$10,
                        $11,$12,$13,$14,
                        $15,$16,
                        $17
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    row["id"],
                    row["anomaly_id"],
                    row["service_id"],
                    row.get("rule_id"),
                    row.get("rule_version"),
                    row["action"],
                    json.dumps(row.get("action_params") or {}),
                    row.get("detection_conf", 0),
                    row.get("rule_conf", 0),
                    row.get("final_conf", 0),
                    row.get("base_risk"),
                    row.get("blast_factor", 1.0),
                    row.get("centrality", 1.0),
                    row.get("effective_severity", 0),
                    row.get("policy_outcome", "UNVALIDATED"),
                    row.get("policy_reason"),
                    json.dumps(row.get("context") or {}),
                )
                return True
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("save_decision failed: %s", e)
                return False

postgres_store = PostgresStore()