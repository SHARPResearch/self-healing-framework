import logging
from app.persistence.postgres import postgres_store
from app.persistence.timescale import timescale_store
from app.persistence.neo4j import neo4j_store
from app.persistence.schemas import POSTGRES_SCHEMA, TIMESCALE_SCHEMA

log = logging.getLogger(__name__)


async def run_migrations():
    log.info("Running migrations on Neon (anomaly_db)")
    await postgres_store.ensure_schema(POSTGRES_SCHEMA)

    log.info("Running migrations on Tiger Cloud (telemetry_db)")
    await timescale_store.ensure_schema(TIMESCALE_SCHEMA)

    log.info("Running migrations on Neo4j Aura")
    await neo4j_store.ensure_schema()

    log.info("All migrations complete")