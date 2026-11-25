# app/core/models.py
 
from pydantic import BaseModel, Field
from typing import Literal

class ServiceNode(BaseModel):
    id: str
    name: str
    namespace: str = "default"
    kind: str = "Service"
    criticality: float = 1.0
    health: Literal["healthy", "degraded", "down", "watch", "critical"] = "healthy"
    metadata: dict = Field(default_factory=dict)

class DependencyEdge(BaseModel):
    source: str                      # consumer service id
    target: str                      # provider service id
    strength: float = 1.0            # 0..1 — call volume / coupling
    protocol: str = "http"
    metadata: dict = Field(default_factory=dict)

class DependencyGraph(BaseModel):
    nodes: list[ServiceNode]
    edges: list[DependencyEdge]