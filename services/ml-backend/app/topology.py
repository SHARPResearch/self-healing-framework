# services/ml-backend/app/topology.py
"""
Dependency topology served to Component 2.

Component 1 owns the service graph: it is the one component that sees every
service in the fleet, so it is the natural authority on what depends on what.
Component 2's dependency graph manager loads this through ``GET /api/topology``
instead of reading a private seed file, which is what the Component 2 report
calls the "Graph Query" input.

Generated from the canonical topology seed — edit the edge list here and every
consumer picks it up on its next refresh.
"""
from __future__ import annotations

import hashlib
import json

#: The service fleet. ``criticality`` is 0..1 and is the weight Component 2's
#: blast-radius analysis multiplies by dependency strength.
NODES: list[dict] = [
    {
        "id": 'waf-proxy',
        "name": 'WAF Proxy',
        "namespace": 'services',
        "criticality": 0.8,
        "health": 'healthy',
    },
    {
        "id": 'api-gateway',
        "name": 'API Gateway',
        "namespace": 'services',
        "criticality": 1.0,
        "health": 'healthy',
    },
    {
        "id": 'web-bff',
        "name": 'Web BFF',
        "namespace": 'services',
        "criticality": 0.9,
        "health": 'healthy',
    },
    {
        "id": 'mobile-bff',
        "name": 'Mobile BFF',
        "namespace": 'services',
        "criticality": 0.85,
        "health": 'healthy',
    },
    {
        "id": 'auth-service',
        "name": 'Auth Service',
        "namespace": 'services',
        "criticality": 0.95,
        "health": 'healthy',
    },
    {
        "id": 'user-service',
        "name": 'User Service',
        "namespace": 'services',
        "criticality": 0.75,
        "health": 'healthy',
    },
    {
        "id": 'orders-service',
        "name": 'Orders Service',
        "namespace": 'services',
        "criticality": 0.9,
        "health": 'healthy',
    },
    {
        "id": 'payment-service',
        "name": 'Payment Service',
        "namespace": 'services',
        "criticality": 0.95,
        "health": 'healthy',
    },
    {
        "id": 'inventory-service',
        "name": 'Inventory Service',
        "namespace": 'services',
        "criticality": 0.7,
        "health": 'healthy',
    },
    {
        "id": 'shipping-service',
        "name": 'Shipping Service',
        "namespace": 'services',
        "criticality": 0.6,
        "health": 'healthy',
    },
    {
        "id": 'notification-service',
        "name": 'Notification Service',
        "namespace": 'services',
        "criticality": 0.55,
        "health": 'healthy',
    },
    {
        "id": 'search-service',
        "name": 'Search Service',
        "namespace": 'services',
        "criticality": 0.7,
        "health": 'healthy',
    },
    {
        "id": 'postgres-primary',
        "name": 'Postgres Primary',
        "namespace": 'services',
        "criticality": 1.0,
        "health": 'healthy',
    },
    {
        "id": 'redis-cache',
        "name": 'Redis Cache',
        "namespace": 'services',
        "criticality": 0.9,
        "health": 'healthy',
    },
    {
        "id": 'kafka-broker',
        "name": 'Kafka Broker',
        "namespace": 'services',
        "criticality": 0.9,
        "health": 'healthy',
    },
    {
        "id": 'metrics-collector',
        "name": 'Metrics Collector',
        "namespace": 'services',
        "criticality": 0.4,
        "health": 'healthy',
    },
]

#: Directed ``source -> target`` means "source calls target", so the reverse
#: reachable set from a service is exactly the blast radius of acting on it.
EDGES: list[dict] = [
    {
        "source": 'waf-proxy',
        "target": 'api-gateway',
        "strength": 1.0,
        "protocol": 'http',
    },
    {
        "source": 'api-gateway',
        "target": 'web-bff',
        "strength": 0.9,
        "protocol": 'http',
    },
    {
        "source": 'api-gateway',
        "target": 'mobile-bff',
        "strength": 0.85,
        "protocol": 'http',
    },
    {
        "source": 'web-bff',
        "target": 'auth-service',
        "strength": 0.9,
        "protocol": 'grpc',
    },
    {
        "source": 'web-bff',
        "target": 'orders-service',
        "strength": 0.95,
        "protocol": 'grpc',
    },
    {
        "source": 'web-bff',
        "target": 'search-service',
        "strength": 0.7,
        "protocol": 'grpc',
    },
    {
        "source": 'mobile-bff',
        "target": 'auth-service',
        "strength": 0.85,
        "protocol": 'grpc',
    },
    {
        "source": 'mobile-bff',
        "target": 'orders-service',
        "strength": 0.9,
        "protocol": 'grpc',
    },
    {
        "source": 'orders-service',
        "target": 'payment-service',
        "strength": 0.9,
        "protocol": 'grpc',
    },
    {
        "source": 'orders-service',
        "target": 'inventory-service',
        "strength": 0.8,
        "protocol": 'grpc',
    },
    {
        "source": 'orders-service',
        "target": 'shipping-service',
        "strength": 0.6,
        "protocol": 'grpc',
    },
    {
        "source": 'orders-service',
        "target": 'notification-service',
        "strength": 0.5,
        "protocol": 'async',
    },
    {
        "source": 'auth-service',
        "target": 'user-service',
        "strength": 0.8,
        "protocol": 'grpc',
    },
    {
        "source": 'payment-service',
        "target": 'notification-service',
        "strength": 0.6,
        "protocol": 'async',
    },
    {
        "source": 'shipping-service',
        "target": 'notification-service',
        "strength": 0.7,
        "protocol": 'async',
    },
    {
        "source": 'search-service',
        "target": 'inventory-service',
        "strength": 0.7,
        "protocol": 'grpc',
    },
    {
        "source": 'search-service',
        "target": 'user-service',
        "strength": 0.5,
        "protocol": 'grpc',
    },
    {
        "source": 'auth-service',
        "target": 'postgres-primary',
        "strength": 1.0,
        "protocol": 'tcp',
    },
    {
        "source": 'auth-service',
        "target": 'redis-cache',
        "strength": 0.9,
        "protocol": 'tcp',
    },
    {
        "source": 'user-service',
        "target": 'postgres-primary',
        "strength": 1.0,
        "protocol": 'tcp',
    },
    {
        "source": 'user-service',
        "target": 'redis-cache',
        "strength": 0.8,
        "protocol": 'tcp',
    },
    {
        "source": 'orders-service',
        "target": 'postgres-primary',
        "strength": 1.0,
        "protocol": 'tcp',
    },
    {
        "source": 'orders-service',
        "target": 'redis-cache',
        "strength": 0.9,
        "protocol": 'tcp',
    },
    {
        "source": 'orders-service',
        "target": 'kafka-broker',
        "strength": 0.8,
        "protocol": 'tcp',
    },
    {
        "source": 'payment-service',
        "target": 'postgres-primary',
        "strength": 1.0,
        "protocol": 'tcp',
    },
    {
        "source": 'payment-service',
        "target": 'kafka-broker',
        "strength": 0.8,
        "protocol": 'tcp',
    },
    {
        "source": 'inventory-service',
        "target": 'postgres-primary',
        "strength": 1.0,
        "protocol": 'tcp',
    },
    {
        "source": 'inventory-service',
        "target": 'redis-cache',
        "strength": 0.85,
        "protocol": 'tcp',
    },
    {
        "source": 'shipping-service',
        "target": 'postgres-primary',
        "strength": 1.0,
        "protocol": 'tcp',
    },
    {
        "source": 'notification-service',
        "target": 'kafka-broker',
        "strength": 1.0,
        "protocol": 'tcp',
    },
    {
        "source": 'search-service',
        "target": 'redis-cache',
        "strength": 0.9,
        "protocol": 'tcp',
    },
    {
        "source": 'metrics-collector',
        "target": 'kafka-broker',
        "strength": 0.5,
        "protocol": 'tcp',
    },
    {
        "source": 'metrics-collector',
        "target": 'postgres-primary',
        "strength": 0.5,
        "protocol": 'tcp',
    },
]


def version() -> str:
    """Content hash, so a consumer can tell whether the graph changed."""
    blob = json.dumps({"nodes": NODES, "edges": EDGES}, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def snapshot() -> dict:
    """The full topology, in the shape Component 2's GraphStore expects."""
    return {"version": version(), "nodes": NODES, "edges": EDGES}
