"""
Neo4j Aura driver for the dependency graph.
"""
import logging
from neo4j import AsyncGraphDatabase
from app.config import settings

log = logging.getLogger(__name__)


class Neo4jStore:
    def __init__(self):
        self.driver = None

    async def connect(self):
        self.driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        await self.driver.verify_connectivity()
        log.info("Connected to Neo4j Aura")

    async def close(self):
        if self.driver:
            await self.driver.close()

    async def ensure_schema(self):
        async with self.driver.session(database=settings.NEO4J_DATABASE) as s:
            await s.run(
                "CREATE CONSTRAINT service_id IF NOT EXISTS "
                "FOR (s:Service) REQUIRE s.id IS UNIQUE"
            )

    async def upsert_graph(self, nodes: list[dict], edges: list[dict]):
        async with self.driver.session(database=settings.NEO4J_DATABASE) as s:
            if nodes:
                await s.run(
                    """
                    UNWIND $nodes AS n
                    MERGE (s:Service {id: n.id})
                    SET s.name        = n.name,
                        s.namespace   = n.namespace,
                        s.criticality = n.criticality,
                        s.health      = n.health
                    """,
                    nodes=nodes,
                )
            if edges:
                await s.run(
                    """
                    UNWIND $edges AS e
                    MATCH (a:Service {id: e.source})
                    MATCH (b:Service {id: e.target})
                    MERGE (a)-[r:DEPENDS_ON]->(b)
                    SET r.strength = e.strength,
                        r.protocol = e.protocol
                    """,
                    edges=edges,
                )

    async def fetch_graph(self) -> dict:
        async with self.driver.session(database=settings.NEO4J_DATABASE) as s:
            nodes_res = await s.run("MATCH (s:Service) RETURN s")
            nodes = [dict(rec["s"]) async for rec in nodes_res]

            edges_res = await s.run(
                "MATCH (a:Service)-[r:DEPENDS_ON]->(b:Service) "
                "RETURN a.id AS source, b.id AS target, "
                "r.strength AS strength, r.protocol AS protocol"
            )
            edges = [dict(rec) async for rec in edges_res]
            return {"nodes": nodes, "edges": edges}


neo4j_store = Neo4jStore()