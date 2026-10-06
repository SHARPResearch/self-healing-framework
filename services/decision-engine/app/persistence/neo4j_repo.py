# app/persistence/neo4j_repo.py
from neo4j import AsyncGraphDatabase
from app.core.models import DependencyGraph

class Neo4jRepository:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def upsert_graph(self, graph: DependencyGraph) -> None:
        async with self.driver.session() as s:
            await s.run("""
                UNWIND $nodes AS n
                MERGE (s:Service {id: n.id})
                SET s.name = n.name, s.namespace = n.namespace,
                    s.criticality = n.criticality, s.health = n.health
            """, nodes=[n.model_dump() for n in graph.nodes])

            await s.run("""
                UNWIND $edges AS e
                MATCH (a:Service {id: e.source})
                MATCH (b:Service {id: e.target})
                MERGE (a)-[r:DEPENDS_ON]->(b)
                SET r.strength = e.strength, r.protocol = e.protocol
            """, edges=[e.model_dump() for e in graph.edges])

    async def load_graph(self) -> DependencyGraph:
        async with self.driver.session() as s:
            nodes = await (await s.run(
                "MATCH (s:Service) RETURN s")).data()
            edges = await (await s.run(
                "MATCH (a:Service)-[r:DEPENDS_ON]->(b:Service) "
                "RETURN a.id AS source, b.id AS target, r.strength AS strength, r.protocol AS protocol"
            )).data()
        # ...convert to models...