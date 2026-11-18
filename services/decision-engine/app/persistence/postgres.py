# services\decision-engine\app\persistence\postgres.py

"""
Async pool for the anomaly events DB (Neon Postgres).
"""
import asyncpg
import json
import logging
from typing import Optional
from app.config import settings

log = logging.getLogger(__name__)


def _json_safe(value):
    """
    json.dumps with a str fallback for non-serializable types (datetime,
    Decimal, UUID, ...). Decision context can legitimately contain raw
    anomaly rows whose datetimes previously crashed persistence.
    """
    return json.dumps(value, default=str)


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
        backfill_max_age_sec: int = 86400,
    ) -> list[dict]:
        """
        Return anomalies that do NOT already have a row in decision_log.

        Ordering is oldest-first and there is deliberately NO tight upper
        cutoff: an anomaly that was missed while the pipeline was down (or
        that is simply older than the poll window) must still be decided on
        the next cycle — otherwise it is silently orphaned forever ("stored
        in the DB, never decided, never notified").

        `window_sec` is kept for API compatibility but only acts as the
        *recent* priority band; `backfill_max_age_sec` is a generous safety
        cap so a pathological backlog can't flood a single cycle.

        Used by the pipeline job to avoid re-deciding on already-handled
        anomalies.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT a.*
                FROM anomaly_events a
                LEFT JOIN decision_log d ON d.anomaly_id = a.id
                WHERE d.id IS NULL
                  AND a.detected_at >= NOW() - INTERVAL '1 second' * $1
                ORDER BY a.detected_at ASC
                LIMIT $2
                """,
                backfill_max_age_sec,
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
                    _json_safe(row.get("action_params") or {}),
                    row.get("detection_conf", 0),
                    row.get("rule_conf", 0),
                    row.get("final_conf", 0),
                    row.get("base_risk"),
                    row.get("blast_factor", 1.0),
                    row.get("centrality", 1.0),
                    row.get("effective_severity", 0),
                    row.get("policy_outcome", "UNVALIDATED"),
                    row.get("policy_reason"),
                    _json_safe(row.get("context") or {}),
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

    # ── ENGINE SETTINGS ─────────────────────────────────────────
    async def list_settings(self) -> dict[str, Any]:
        """All persisted setting overrides as {key: value}."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM engine_settings")
        out: dict[str, Any] = {}
        for r in rows:
            v = r["value"]
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except Exception:
                    pass
            out[r["key"]] = v
        return out

    async def save_setting(self, key: str, value: Any, actor: str = "unknown") -> None:
        """Upsert one setting row."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO engine_settings (key, value, updated_by, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value      = EXCLUDED.value,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = NOW()
                """,
                key,
                json.dumps(value),
                actor or "unknown",
            )

    async def save_settings_audit(
        self,
        key: str,
        old_value: Any,
        new_value: Any,
        actor: str = "unknown",
    ) -> None:
        """Append one row to settings_audit. Never raises into the caller."""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO settings_audit (key, old_value, new_value, actor)
                    VALUES ($1, $2, $3, $4)
                    """,
                    key,
                    json.dumps(old_value) if old_value is not None else None,
                    json.dumps(new_value) if new_value is not None else None,
                    actor or "unknown",
                )
            except Exception as e:
                log.exception("save_settings_audit failed for %s: %s", key, e)

    async def list_settings_audit(self, limit: int = 100) -> list[dict]:
        """Settings audit history, newest first."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, key, old_value, new_value, actor, created_at
                FROM settings_audit
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        out = []
        for r in rows:
            row = dict(r)
            if hasattr(row.get("created_at"), "isoformat"):
                row["created_at"] = row["created_at"].isoformat()
            out.append(row)
        return out

    # ── NOTIFICATIONS ───────────────────────────────────────────
    async def save_notification(self, row: dict) -> None:
        """Insert one notification log row. Never raises into the caller."""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO notifications (
                        id, kind, anomaly_id, decision_id, service_id,
                        recipient, sender, subject, body, status, error, sent_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    row["id"],
                    row["kind"],
                    row.get("anomaly_id"),
                    row.get("decision_id"),
                    row.get("service_id"),
                    row["recipient"],
                    row.get("sender"),
                    row["subject"],
                    row.get("body"),
                    row.get("status", "PENDING"),
                    row.get("error"),
                    row.get("sent_at"),
                )
            except Exception as e:
                log.exception("save_notification failed: %s", e)

    async def list_notifications(self, limit: int = 100) -> list[dict]:
        """Recent notifications, newest first."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, kind, anomaly_id, decision_id, service_id,
                       recipient, sender, subject, status, error,
                       created_at, sent_at
                FROM notifications
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        out = []
        for r in rows:
            row = dict(r)
            for k in ("created_at", "sent_at"):
                if hasattr(row.get(k), "isoformat"):
                    row[k] = row[k].isoformat()
            out.append(row)
        return out

        # ── IN_FLIGHT ACTIONS (Phase 2 — conflict detection) ────────
    async def insert_in_flight(
        self,
        decision_id: str,
        service_id: str,
        action: str,
        expires_at,
    ) -> bool:
        """
        Register an action as "in progress" on a service. Called by the
        decision pipeline right after a decision is persisted.
        """
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO in_flight_actions
                        (decision_id, service_id, action, started_at, expires_at)
                    VALUES ($1, $2, $3, NOW(), $4)
                    ON CONFLICT (decision_id) DO NOTHING
                    """,
                    decision_id, service_id, action, expires_at,
                )
                return True
            except Exception as e:
                log.exception("insert_in_flight failed: %s", e)
                return False

    async def list_in_flight(self, service_id: str) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM in_flight_actions
                WHERE service_id = $1
                ORDER BY started_at DESC
                """,
                service_id,
            )
        return [dict(r) for r in rows]

    async def list_in_flight_multi(self, service_ids: list[str]) -> list[dict]:
        if not service_ids:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM in_flight_actions
                WHERE service_id = ANY($1::text[])
                ORDER BY started_at DESC
                """,
                service_ids,
            )
        return [dict(r) for r in rows]

    async def clear_expired_in_flight(self) -> int:
        """Housekeeping — call from a background job if you like."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM in_flight_actions WHERE expires_at < NOW()"
            )
        # "DELETE N"
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0

    # ── ACTION HISTORY (Phase 2 — repeat-failure counting) ──────
    async def record_action_outcome(
        self,
        decision_id: str,
        service_id: str,
        action: str,
        outcome: str,          # SUCCESS | FAILED | NEUTRAL | UNKNOWN
    ) -> bool:
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO action_history
                        (decision_id, service_id, action, outcome, occurred_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    """,
                    decision_id, service_id, action, outcome,
                )
                return True
            except Exception as e:
                log.exception("record_action_outcome failed: %s", e)
                return False

    async def count_recent_failures(
        self,
        service_id: str,
        action: str,
        window_min: int = 30,
    ) -> int:
        """
        Number of FAILED outcomes for this (service, action) in the window.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS n
                FROM action_history
                WHERE service_id = $1
                  AND action = $2
                  AND outcome = 'FAILED'
                  AND occurred_at >= NOW() - INTERVAL '1 minute' * $3
                """,
                service_id, action, window_min,
            )
        return int(row["n"]) if row else 0

    # ── SHADOW RECORDS (Phase 2 — Shadow Mode) ──────────────────
    async def save_shadow_record(self, payload: dict) -> bool:
        """
        Persist one shadow_records row. `payload` matches the shape
        produced by validation.shadow.build_shadow_payload.
        """
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO shadow_records (
                        id, decision_id, anomaly_id, service_id,
                        candidate_action, confidence, risk,
                        simulated_outcome, actual_outcome, verdict, learning,
                        observed_at, created_at
                    ) VALUES (
                        $1, $2, $3, $4,
                        $5, $6, $7,
                        $8, $9, $10, $11,
                        NULL, NOW()
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    payload["SHADOW_ID"],
                    payload["DECISION_ID"],
                    payload["ANOMALY_ID"],
                    payload["SERVICE"],
                    payload["CANDIDATE_ACTION"],
                    payload["CONFIDENCE"],
                    payload["RISK"],
                    _json_safe(payload.get("SIMULATED_OUTCOME") or {}),
                    _json_safe(payload.get("ACTUAL_OUTCOME")) if payload.get("ACTUAL_OUTCOME") else None,
                    payload.get("VERDICT"),
                    payload.get("LEARNING"),
                )
                return True
            except Exception as e:
                log.exception("save_shadow_record failed: %s", e)
                return False
    
        # ── COOLDOWNS (Phase 3) ──────────────────────────────────────
    async def upsert_cooldown(
        self,
        service_id: str,
        decision_id: str,
        expires_at,
    ) -> bool:
        """
        Start / extend the cooldown for a service. Source of truth —
        Redis (or in-memory) is only a cache in front of this.
        """
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO cooldowns (service_id, decision_id, started_at, expires_at)
                    VALUES ($1, $2, NOW(), $3)
                    ON CONFLICT (service_id) DO UPDATE SET
                        decision_id = EXCLUDED.decision_id,
                        started_at  = EXCLUDED.started_at,
                        expires_at  = EXCLUDED.expires_at
                    """,
                    service_id, decision_id, expires_at,
                )
                return True
            except Exception as e:
                log.exception("upsert_cooldown failed: %s", e)
                return False

    async def get_active_cooldown(self, service_id: str) -> dict | None:
        """Return the cooldown row for a service if it has not yet expired."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT service_id, decision_id, started_at, expires_at
                FROM cooldowns
                WHERE service_id = $1
                  AND expires_at > NOW()
                """,
                service_id,
            )
        return dict(row) if row else None

    # ── IDEMPOTENCY (Phase 3) ───────────────────────────────────
    async def get_idempotency_key(self, key: str) -> dict | None:
        """Return the row for a key if it has not yet expired."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT key, decision_id, created_at, expires_at
                FROM idempotency_keys
                WHERE key = $1
                  AND expires_at > NOW()
                """,
                key,
            )
        return dict(row) if row else None

    async def save_idempotency_key(
        self,
        key: str,
        decision_id: str,
        expires_at,
    ) -> bool:
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO idempotency_keys (key, decision_id, created_at, expires_at)
                    VALUES ($1, $2, NOW(), $3)
                    ON CONFLICT (key) DO NOTHING
                    """,
                    key, decision_id, expires_at,
                )
                return True
            except Exception as e:
                log.exception("save_idempotency_key failed: %s", e)
                return False

    # ── ACTION COUNT (Phase 3 — action_counter guardrail) ────────
    async def count_recent_actions(
        self,
        service_id: str,
        window_min: int = 60,
    ) -> int:
        """
        Number of actions on this service in the last `window_min` minutes.
        Derived from `action_history` — no separate counter table.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS n
                FROM action_history
                WHERE service_id = $1
                  AND occurred_at >= NOW() - INTERVAL '1 minute' * $2
                """,
                service_id, window_min,
            )
        return int(row["n"]) if row else 0
    
        # ── ESCALATIONS (Phase 4) ────────────────────────────────────
    async def save_escalation(self, payload: dict) -> bool:
        """
        Upsert an escalation row. `payload` is Escalation.to_dict() shape.
        """
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO escalations (
                        id, decision_id, anomaly_id, service_id,
                        status, attempt, max_attempts,
                        notifications, response, failure_report,
                        next_attempt_at, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4,
                        $5, $6, $7,
                        $8, $9, $10,
                        $11, NOW(), NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        status          = EXCLUDED.status,
                        attempt         = EXCLUDED.attempt,
                        notifications   = EXCLUDED.notifications,
                        response        = EXCLUDED.response,
                        failure_report  = EXCLUDED.failure_report,
                        next_attempt_at = EXCLUDED.next_attempt_at,
                        updated_at      = NOW()
                    """,
                    payload["id"],
                    payload["decision_id"],
                    payload["anomaly_id"],
                    payload["service_id"],
                    payload["status"],
                    payload["attempt"],
                    payload["max_attempts"],
                    _json_safe(payload.get("notifications") or []),
                    _json_safe(payload.get("response")) if payload.get("response") else None,
                    payload.get("failure_report"),
                    payload.get("next_attempt_at"),
                )
                return True
            except Exception as e:
                log.exception("save_escalation failed: %s", e)
                return False

    async def get_escalation(self, escalation_id: str) -> dict | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM escalations WHERE id = $1",
                escalation_id,
            )
        return dict(row) if row else None

    async def list_escalations(
        self,
        statuses: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict]:
        if statuses:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM escalations
                    WHERE status = ANY($1::text[])
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    statuses, limit,
                )
        else:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM escalations ORDER BY created_at DESC LIMIT $1",
                    limit,
                )
        return [dict(r) for r in rows]

    async def list_escalations_due(self, now=None) -> list[dict]:
        """
        Escalations whose next_attempt_at is <= now and status is not terminal.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM escalations
                WHERE next_attempt_at IS NOT NULL
                  AND next_attempt_at <= NOW()
                  AND status IN ('PENDING', 'AWAITING_HUMAN')
                ORDER BY next_attempt_at ASC
                LIMIT 200
                """
            )
        return [dict(r) for r in rows]

    # ── SHADOW RECORDS (Phase A — observer + metrics) ───────────
    async def list_open_shadows(self, min_age_sec: int = 300, limit: int = 200) -> list[dict]:
        """
        Shadow rows that:
          * have no verdict yet
          * are at least min_age_sec old (so the anomaly had a chance to resolve)
        Ordered oldest-first so we handle the longest-waiting rows first.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM shadow_records
                WHERE verdict IS NULL
                  AND actual_outcome IS NULL
                  AND created_at <= NOW() - INTERVAL '1 second' * $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                min_age_sec, limit,
            )
        return [dict(r) for r in rows]

    async def get_shadow(self, shadow_id: str) -> dict | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM shadow_records WHERE id = $1", shadow_id
            )
        return dict(row) if row else None

    async def update_shadow_outcome(
        self,
        shadow_id: str,
        *,
        actual_outcome: dict,
        verdict: str,
        learning: str,
        observed_at,
        resolved_at,
    ) -> bool:
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    UPDATE shadow_records
                    SET actual_outcome = $2,
                        verdict        = $3,
                        learning       = $4,
                        observed_at    = $5,
                        resolved_at    = $6
                    WHERE id = $1
                      AND verdict IS NULL
                    """,
                    shadow_id,
                    _json_safe(actual_outcome),
                    verdict,
                    learning,
                    observed_at,
                    resolved_at,
                )
                return True
            except Exception as e:
                log.exception("update_shadow_outcome failed: %s", e)
                return False

    async def mark_shadow_abandoned(
        self,
        *,
        shadow_id: str,
        reason: str,
        observed_at,
    ) -> bool:
        """
        Terminal, no verdict. Used when the anomaly never resolved
        within SHADOW_MAX_WAIT_MIN (so we can't compare outcomes).
        """
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    UPDATE shadow_records
                    SET verdict     = $2,
                        learning    = $3,
                        observed_at = $4
                    WHERE id = $1
                      AND verdict IS NULL
                    """,
                    shadow_id,
                    reason,
                    f"anomaly never resolved within budget ({reason})",
                    observed_at,
                )
                return True
            except Exception as e:
                log.exception("mark_shadow_abandoned failed: %s", e)
                return False

    async def list_shadows(
        self,
        limit: int = 100,
        verdict: str | None = None,
        service_id: str | None = None,
    ) -> list[dict]:
        clauses = []
        args: list = []
        if verdict:
            args.append(verdict)
            clauses.append(f"verdict = ${len(args)}")
        if service_id:
            args.append(service_id)
            clauses.append(f"service_id = ${len(args)}")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        args.append(limit)
        sql = f"""
            SELECT * FROM shadow_records
            {where}
            ORDER BY created_at DESC
            LIMIT ${len(args)}
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]

    async def get_escalation_by_decision(self, decision_id: str) -> dict | None:
        """
        Return the (most recent) escalation row for a decision_id.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM escalations
                WHERE decision_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                decision_id,
            )
        return dict(row) if row else None

    async def shadow_metrics(self) -> dict:
        """
        Aggregate metrics for the research chapter §8.2.

        Returns:
            total_shadows        — all shadow records, any state
            open                 — verdict IS NULL
            resolved_naturally   — self-resolved without action
            would_have_helped    — would have shortened resolution
            unnecessary          — action would have been wasted
            unknown              — operator declined / data insufficient
            still_active         — anomaly never resolved within budget
            unnecessary_action_rate = unnecessary / (unnecessary + would_have_helped)
            mean_resolution_time_sec — for resolved_naturally rows only
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                                                    AS total,
                    COUNT(*) FILTER (WHERE verdict IS NULL)                     AS open,
                    COUNT(*) FILTER (WHERE verdict = 'ACTION_WOULD_HAVE_BEEN_UNNECESSARY') AS unnecessary,
                    COUNT(*) FILTER (WHERE verdict = 'ACTION_WOULD_HAVE_HELPED') AS would_have_helped,
                    COUNT(*) FILTER (WHERE verdict = 'UNKNOWN')                 AS unknown,
                    COUNT(*) FILTER (WHERE verdict = 'ANOMALY_STILL_ACTIVE')    AS still_active,
                    AVG(
                        (actual_outcome->>'RESOLUTION_TIME_SEC')::float
                    ) FILTER (
                        WHERE actual_outcome->>'ANOMALY_RESOLVED_NATURALLY' = 'true'
                    ) AS mean_resolution_sec
                FROM shadow_records
                """
            )
        if not row:
            return {
                "total_shadows": 0, "open": 0,
                "resolved_naturally": 0, "would_have_helped": 0,
                "unnecessary": 0, "unknown": 0, "still_active": 0,
                "unnecessary_action_rate": 0.0,
                "mean_resolution_time_sec": 0.0,
            }

        d = dict(row)
        unnecessary = int(d.get("unnecessary") or 0)
        helpful = int(d.get("would_have_helped") or 0)
        denom = unnecessary + helpful
        rate = round(unnecessary / denom, 4) if denom else 0.0

        return {
            "total_shadows": int(d.get("total") or 0),
            "open": int(d.get("open") or 0),
            # Note: "resolved_naturally" isn't a stored verdict, it's
            # inferred from actual_outcome. Count it here for completeness:
            "resolved_naturally": int(d.get("unnecessary") or 0)
                                + int(d.get("would_have_helped") or 0),
            "would_have_helped": helpful,
            "unnecessary": unnecessary,
            "unknown": int(d.get("unknown") or 0),
            "still_active": int(d.get("still_active") or 0),
            "unnecessary_action_rate": rate,
            "mean_resolution_time_sec": round(float(d.get("mean_resolution_sec") or 0.0), 2),
        }

postgres_store = PostgresStore()