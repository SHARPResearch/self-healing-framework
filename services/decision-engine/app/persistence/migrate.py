# decision-engine\app\persistence\migrate.py
"""
Runs all DDL on startup (idempotent).

Order matters:
    1. Neo4j schema (constraints + indexes)
    2. Neon Postgres base schema (anomaly_events)
    3. Neon Postgres Batch 1 schema (rules, decision_log, shadow_records,
       escalations, action_history, in_flight_actions)
    4. Tiger Cloud Timescale schema (infra_snapshots, app_snapshots)

Every DDL uses `IF NOT EXISTS` so this is safe to run on every boot.
"""
import logging

from app.persistence.postgres import postgres_store
from app.persistence.timescale import timescale_store
from app.persistence.neo4j import neo4j_store
from app.persistence.schemas import (
    POSTGRES_SCHEMA,
    TIMESCALE_SCHEMA,
    BATCH1_DDL,          # ★ NEW
)

log = logging.getLogger(__name__)


async def run_migrations():
    # ── 1. Neo4j ────────────────────────────────────────────────
    log.info("Running migrations on Neo4j Aura")
    await neo4j_store.ensure_schema()

    # ── 2. Neon — base tables ───────────────────────────────────
    log.info("Running migrations on Neon (anomaly_db) — base schema")
    await postgres_store.ensure_schema(POSTGRES_SCHEMA)

    # ── 3. Neon — Component 2 tables ────────────────────────────
    log.info(
        "Running migrations on Neon (anomaly_db) — %d Component 2 tables",
        len(BATCH1_DDL),
    )
    for i, ddl in enumerate(BATCH1_DDL, start=1):
        # Grab the first CREATE TABLE line for logging
        first_line = next(
            (ln.strip() for ln in ddl.splitlines() if "CREATE TABLE" in ln),
            f"DDL block #{i}",
        )
        log.debug("  → %s", first_line)
        await postgres_store.ensure_schema(ddl)

    # ── 4. Tiger Cloud ──────────────────────────────────────────
    log.info("Running migrations on Tiger Cloud (telemetry_db)")
    await timescale_store.ensure_schema(TIMESCALE_SCHEMA)

    log.info("All migrations complete")