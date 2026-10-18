# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from app.api.routes import graph, health, mock_data
# from app.topology.sources.static_source import load_static_topology

# app = FastAPI(title="Decision Engine — Dependency Graph Manager")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(graph.router)
# app.include_router(health.router)
# app.include_router(mock_data.router)


# @app.on_event("startup")
# async def startup():
#     load_static_topology("seeds/topology.yaml")
#     print("✅ Topology loaded from seeds/topology.yaml")

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.api.routes import (
    graph, health, mock_data, anomaly_evidence, telemetry_history,
)
from app.topology.sources.static_source import load_static_topology
from app.persistence.postgres import postgres_store
from app.persistence.timescale import timescale_store
from app.persistence.neo4j import neo4j_store
from app.persistence.migrate import run_migrations
from app.ingestion.telemetry_puller import start_telemetry_puller, pull_once
from app.ingestion.anomaly_sink import start_anomaly_sink, resume_pending_snapshots
from app.api.routes import (
    graph, health, mock_data, anomaly_evidence, telemetry_history,
    rules, decisions,                            
)
from app.rules.registry import rule_registry    

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("decision-engine")

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()

    log.info("Connecting to Neon (anomaly_db)")
    await postgres_store.connect()

    log.info("Connecting to Tiger Cloud (telemetry_db)")
    await timescale_store.connect()

    log.info("Connecting to Neo4j Aura")
    await neo4j_store.connect()

    await run_migrations()

    # Load seed topology into memory
    load_static_topology("seeds/topology.yaml")

    # ★ BATCH 1 — seed rules (first boot only) then load into memory
    inserted = await rule_registry.seed_if_empty()
    if inserted:
        log.info("Seeded %d starter rules", inserted)
    await rule_registry.load_from_db()
    log.info("RuleRegistry ready (%d rules)", rule_registry.count())

    # Push topology to Neo4j so Aura is populated
    from app.core.graph_store import GraphStore
    snapshot = GraphStore().snapshot()
    await neo4j_store.upsert_graph(
        nodes=[
            {
                "id": n.id, "name": n.name, "namespace": n.namespace,
                "criticality": n.criticality, "health": n.health,
            }
            for n in snapshot.nodes
        ],
        edges=[
            {
                "source": e.source, "target": e.target,
                "strength": e.strength, "protocol": e.protocol,
            }
            for e in snapshot.edges
        ],
    )
    log.info("Topology pushed to Neo4j (%d nodes, %d edges)",
             len(snapshot.nodes), len(snapshot.edges))

    scheduler.start()
    start_telemetry_puller(scheduler)
    start_anomaly_sink(scheduler)
    await resume_pending_snapshots(scheduler)   
    await pull_once()

    log.info("✅ Decision Engine startup complete")

    yield

    log.info("Shutting down…")
    scheduler.shutdown(wait=False)
    await postgres_store.close()
    await timescale_store.close()
    await neo4j_store.close()


app = FastAPI(
    title="Decision Engine — Cloud (Neon + Tiger + Aura)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph.router)
app.include_router(health.router)
app.include_router(mock_data.router)
app.include_router(anomaly_evidence.router)
app.include_router(telemetry_history.router)
app.include_router(rules.router)  
app.include_router(decisions.router)

@app.get("/api/debug/buffer")
async def debug_buffer():
    from app.ingestion.ring_buffer import ring_buffer
    return ring_buffer.stats()


@app.get("/api/debug/db")
async def debug_db():
    async with postgres_store.pool.acquire() as conn:
        anomaly_count = await conn.fetchval("SELECT COUNT(*) FROM anomaly_events")
    async with timescale_store.pool.acquire() as conn:
        infra_count = await conn.fetchval("SELECT COUNT(*) FROM infra_snapshots")
        app_count = await conn.fetchval("SELECT COUNT(*) FROM app_snapshots")
    return {
        "anomalies": anomaly_count,
        "infra_snapshots": infra_count,
        "app_snapshots": app_count,
    }