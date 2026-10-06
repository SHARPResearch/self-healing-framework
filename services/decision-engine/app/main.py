from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import graph, health, mock_data
from app.topology.sources.static_source import load_static_topology

app = FastAPI(title="Decision Engine — Dependency Graph Manager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph.router)
app.include_router(health.router)
app.include_router(mock_data.router)


@app.on_event("startup")
async def startup():
    load_static_topology("seeds/topology.yaml")
    print("✅ Topology loaded from seeds/topology.yaml")