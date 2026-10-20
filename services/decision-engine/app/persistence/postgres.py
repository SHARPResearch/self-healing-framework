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

    async def get_anomalies_without_decisions(
        self,
        window_sec: int = 300,
        limit: int = 100,
    ) -> list[dict]:
        """
        Return anomalies from the last `window_sec` seconds that do NOT
        already have a row in decision_log.

        Used by the pipeline job to avoid re-deciding on already-handled
        anomalies.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT a.*
                FROM anomaly_events a
                LEFT JOIN decision_log d ON d.anomaly_id = a.id
                WHERE a.detected_at >= NOW() - INTERVAL '1 second' * $1
                  AND d.id IS NULL
                ORDER BY a.detected_at ASC
                LIMIT $2
                """,
                window_sec,
                limit,
            )
        return [dict(r) for r in rows]
    
    # ── INCIDENT LIFECYCLE ─────────────────────────────────────
    async def get_incident_state(self, service_id: str) -> dict | None:
        """Return the current incident state row for a service, or None."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM incident_state WHERE service_id = $1",
                service_id,
            )
        return dict(row) if row else None

    async def get_all_incident_states(self) -> list[dict]:
        """Return all incident state rows. Used by debug endpoint."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM incident_state ORDER BY updated_at DESC"
            )
        return [dict(r) for r in rows]

    async def set_incident_state(
        self,
        service_id: str,
        current_health: str,
        incident_start=None,
        incident_id: str | None = None,
    ) -> None:
        """
        Upsert incident state. Pass incident_start=None to mark as healthy.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO incident_state
                    (service_id, current_health, incident_start, incident_id,
                     last_seen_at, updated_at)
                VALUES ($1, $2, $3, $4, NOW(), NOW())
                ON CONFLICT (service_id) DO UPDATE SET
                    current_health = EXCLUDED.current_health,
                    incident_start = EXCLUDED.incident_start,
                    incident_id    = EXCLUDED.incident_id,
                    last_seen_at   = NOW(),
                    updated_at     = NOW()
                """,
                service_id,
                current_health,
                incident_start,
                incident_id,
            )

    async def close_incident(self, service_id: str) -> None:
        """Mark service as healthy, clear incident fields."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE incident_state
                SET current_health = 'healthy',
                    incident_start = NULL,
                    incident_id    = NULL,
                    last_seen_at   = NOW(),
                    updated_at     = NOW()
                WHERE service_id = $1
                """,
                service_id,
            )

    # ── DECISION LOG — NO MATCH ────────────────────────────────
    async def save_no_match_decision(self, row: dict) -> bool:
        """
        Write a decision row with policy_outcome='NO_RULE_MATCHED'.
        Prevents the pipeline from retrying this anomaly forever.
        """
        return await self.save_decision(row)
    
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

    async def get_decision(self, decision_id: str) -> dict | None:
        """Fetch one decision_log row by id."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM decision_log WHERE id = $1", decision_id
            )
        return dict(row) if row else None
 
    async def list_decisions(
        self,
        limit: int = 50,
        service_id: str | None = None,
        anomaly_id: str | None = None,
        policy_outcome: str | None = None,
    ) -> list[dict]:
        """List recent decision_log rows with optional filters."""
        clauses = []
        args = []
        if service_id:
            args.append(service_id)
            clauses.append(f"service_id = ${len(args)}")
        if anomaly_id:
            args.append(anomaly_id)
            clauses.append(f"anomaly_id = ${len(args)}")
        if policy_outcome:
            args.append(policy_outcome)
            clauses.append(f"policy_outcome = ${len(args)}")

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        args.append(limit)
        sql = f"""
            SELECT * FROM decision_log
            {where}
            ORDER BY created_at DESC
            LIMIT ${len(args)}
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]
    
    async def list_anomalies_with_decisions(
        self,
        limit: int = 100,
    ) -> list[dict]:
        """
        Return anomalies joined with their decision (if any).
        Each row: all anomaly_events columns + decision_* fields (nullable).
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    a.*,
                    d.id               AS decision_id,
                    d.rule_id          AS decision_rule_id,
                    d.action           AS decision_action,
                    d.final_conf       AS decision_final_conf,
                    d.effective_severity AS decision_effective_severity,
                    d.policy_outcome   AS decision_policy_outcome,
                    d.policy_reason    AS decision_policy_reason,
                    d.created_at       AS decision_created_at
                FROM anomaly_events a
                LEFT JOIN decision_log d ON d.anomaly_id = a.id
                ORDER BY a.detected_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [dict(r) for r in rows]

    # ── RULE AUDIT ──────────────────────────────────────────────
    async def save_rule_audit(
        self,
        rule_id: str,
        action: str,
        actor: str = "unknown",
        diff: dict | None = None,
    ) -> None:
        """
        Append one row to rule_audit. Never raises into the caller — audit
        logging must not be able to break a rule write that already worked.
        """
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO rule_audit (rule_id, action, actor, diff)
                    VALUES ($1, $2, $3, $4)
                    """,
                    rule_id,
                    action,
                    actor or "unknown",
                    json.dumps(diff) if diff is not None else None,
                )
            except Exception as e:
                log.exception("save_rule_audit failed for %s: %s", rule_id, e)

    async def list_rule_audit(
        self,
        rule_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """Audit history for one rule, newest first."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, rule_id, action, actor, diff, created_at
                FROM rule_audit
                WHERE rule_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                rule_id,
                limit,
            )
        out = []
        for r in rows:
            row = dict(r)
            if hasattr(row.get("created_at"), "isoformat"):
                row["created_at"] = row["created_at"].isoformat()
            out.append(row)
        return out


postgres_store = PostgresStore()