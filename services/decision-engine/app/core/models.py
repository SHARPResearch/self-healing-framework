# app/core/models.py

from pydantic import BaseModel, Field
from typing import Literal

class ServiceNode(BaseModel):
    id: str                          # e.g. "payment-svc"
    name: str
    namespace: str = "default"
    kind: str = "Service"            # Service | Deployment | Pod
    criticality: float = 1.0         # 0..1, from business rules
    health: Literal["healthy", "degraded", "down"] = "healthy"
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