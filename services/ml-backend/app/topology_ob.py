# services/ml-backend/app/topology_ob.py
"""
Online Boutique call graph.

The replay/SMD topology in ``app/topology.py`` describes a synthetic fleet
(`waf-proxy`, `api-gateway`, `orders-service`, …) that does not exist on the
cluster. In live mode those service ids are meaningless, so Component 2's
centrality and blast-radius would be computed over a graph with no edges to
any live service.

This module is the real thing: the call graph of Google's Online Boutique
v0.10.7, which is what ``infrastructure/online-boutique`` deploys. Edges are
``caller -> callee``, so the reverse-reachable set from a service is exactly
the blast radius of acting on it.

Node ``criticality`` is a static weight (0–1) derived from how central the
service is in this graph: the frontend and checkout sit on every request path,
the leaf services sit on one.
"""
from __future__ import annotations

import hashlib
import json

NAMESPACE = "online-boutique"

#: deployment name -> (display name, static criticality)
NODES = [
    {"id": "frontend", "name": "Frontend", "namespace": NAMESPACE, "criticality": 1.0},
    {"id": "checkoutservice", "name": "Checkout Service", "namespace": NAMESPACE, "criticality": 0.95},
    {"id": "cartservice", "name": "Cart Service", "namespace": NAMESPACE, "criticality": 0.9},
    {"id": "productcatalogservice", "name": "Product Catalog Service", "namespace": NAMESPACE, "criticality": 0.9},
    {"id": "currencyservice", "name": "Currency Service", "namespace": NAMESPACE, "criticality": 0.8},
    {"id": "shippingservice", "name": "Shipping Service", "namespace": NAMESPACE, "criticality": 0.8},
    {"id": "paymentservice", "name": "Payment Service", "namespace": NAMESPACE, "criticality": 0.75},
    {"id": "emailservice", "name": "Email Service", "namespace": NAMESPACE, "criticality": 0.6},
    {"id": "recommendationservice", "name": "Recommendation Service", "namespace": NAMESPACE, "criticality": 0.6},
    {"id": "adservice", "name": "Ad Service", "namespace": NAMESPACE, "criticality": 0.55},
    {"id": "redis-cart", "name": "Redis Cart", "namespace": NAMESPACE, "criticality": 0.65},
    {"id": "loadgenerator", "name": "Load Generator", "namespace": NAMESPACE, "criticality": 0.3},
]

#: caller -> callee, with the relative share of that caller's traffic it carries.
EDGES = [
    {"source": "loadgenerator", "target": "frontend", "strength": 1.0, "protocol": "http"},
    {"source": "frontend", "target": "adservice", "strength": 0.4, "protocol": "grpc"},
    {"source": "frontend", "target": "cartservice", "strength": 0.7, "protocol": "grpc"},
    {"source": "frontend", "target": "checkoutservice", "strength": 0.6, "protocol": "grpc"},
    {"source": "frontend", "target": "currencyservice", "strength": 0.8, "protocol": "grpc"},
    {"source": "frontend", "target": "productcatalogservice", "strength": 0.9, "protocol": "grpc"},
    {"source": "frontend", "target": "recommendationservice", "strength": 0.5, "protocol": "grpc"},
    {"source": "frontend", "target": "shippingservice", "strength": 0.4, "protocol": "grpc"},
    {"source": "checkoutservice", "target": "cartservice", "strength": 0.9, "protocol": "grpc"},
    {"source": "checkoutservice", "target": "currencyservice", "strength": 0.8, "protocol": "grpc"},
    {"source": "checkoutservice", "target": "emailservice", "strength": 0.6, "protocol": "grpc"},
    {"source": "checkoutservice", "target": "paymentservice", "strength": 0.9, "protocol": "grpc"},
    {"source": "checkoutservice", "target": "productcatalogservice", "strength": 0.8, "protocol": "grpc"},
    {"source": "checkoutservice", "target": "shippingservice", "strength": 0.8, "protocol": "grpc"},
    {"source": "recommendationservice", "target": "productcatalogservice", "strength": 1.0, "protocol": "grpc"},
    {"source": "cartservice", "target": "redis-cart", "strength": 1.0, "protocol": "tcp"},
]


def _filter(live: set[str] | None) -> tuple[list[dict], list[dict]]:
    """Keep only nodes (and their edges) that exist in the running fleet."""
    if not live:
        return NODES, EDGES
    nodes = [n for n in NODES if n["id"] in live]
    kept = {n["id"] for n in nodes}
    edges = [e for e in EDGES if e["source"] in kept and e["target"] in kept]
    return nodes, edges


def version(live: set[str] | None = None) -> str:
    nodes, edges = _filter(live)
    blob = json.dumps({"n": nodes, "e": edges}, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def snapshot(live: set[str] | None = None, health: dict[str, str] | None = None) -> dict:
    """The Online Boutique graph, optionally filtered to the live deployments."""
    nodes, edges = _filter(live)
    health = health or {}
    return {
        "version": version(live),
        "mode": "live",
        "namespace": NAMESPACE,
        "nodes": [{**n, "health": health.get(n["id"], "healthy")} for n in nodes],
        "edges": edges,
    }
