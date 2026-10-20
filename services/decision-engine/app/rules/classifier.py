"""
Anomaly classifier — Isolated / Upstream / Cascading.

Definitions (as per Component 2 diagram):

    NORMAL      — no anomaly, or neighbor counts are empty but service is healthy
    ISOLATED    — a single service is unhealthy, no neighbors are unhealthy
    UPSTREAM    — this service's UPSTREAM (what it calls) is unhealthy,
                  but this service's own anomaly is the origin of the cascade
    CASCADING   — this service's DOWNSTREAM (who calls it) is unhealthy,
                  meaning this anomaly is a symptom of a cascade

Rules of thumb:

    If upstream is unhealthy and downstream is healthy  → UPSTREAM
        (the problem comes from what we depend on)

    If downstream is unhealthy and upstream is healthy  → CASCADING
        (our failure is propagating to consumers)

    If both are healthy and no neighbor anomalies       → ISOLATED
        (a single-service incident)

    If both are unhealthy                               → CASCADING
        (worst case; cascade already in flight)
"""
from __future__ import annotations

import logging

from app.rules.context import AnomalyContext, normalize_health

log = logging.getLogger(__name__)


class AnomalyKind:
    NORMAL    = "NORMAL"
    ISOLATED  = "ISOLATED"
    UPSTREAM  = "UPSTREAM"
    CASCADING = "CASCADING"


def classify(ctx: AnomalyContext) -> str:
    """
    Assign a classification label to the context and return it.
    Mutates ctx.kind in place as a convenience.
    """
    kind = _classify(ctx)
    ctx.kind = kind
    return kind


def _classify(ctx: AnomalyContext) -> str:
    # ── No anomaly at all? Then nothing to classify ──────────────
    if not ctx.anomaly:
        return AnomalyKind.NORMAL

    # ── Any neighbor unhealthy? ──────────────────────────────────
    has_up_unhealthy = ctx.upstream_healthy_count < len(ctx.upstream)
    has_down_unhealthy = ctx.downstream_healthy_count < len(ctx.downstream)

    # ── No graph neighbors at all (leaf node) ────────────────────
    if not ctx.upstream and not ctx.downstream:
        return AnomalyKind.ISOLATED

    # ── No unhealthy neighbors → true isolated ───────────────────
    if not has_up_unhealthy and not has_down_unhealthy:
        # One caveat: if this service has huge blast radius (many downstream),
        # treat as UPSTREAM-worthy because fixing it prevents future cascade.
        # But per spec, isolated = no neighbor impact. Keep it simple.
        return AnomalyKind.ISOLATED

    # ── Upstream unhealthy, downstream healthy → UPSTREAM ────────
    if has_up_unhealthy and not has_down_unhealthy:
        return AnomalyKind.UPSTREAM

    # ── Downstream unhealthy, upstream healthy → CASCADING ───────
    if not has_up_unhealthy and has_down_unhealthy:
        return AnomalyKind.CASCADING

    # ── Both unhealthy → cascading (worst case) ──────────────────
    return AnomalyKind.CASCADING


def classify_from_health(
    ctx: AnomalyContext,
    neighbor_health: dict[str, str],
) -> str:
    """
    Alternative entry point when the caller already has a dict of neighbor
    health statuses (e.g. from /api/services). Avoids re-reading the graph.
    """
    up_unhealthy = sum(
        1 for n in ctx.upstream
        if normalize_health(neighbor_health.get(n, "healthy")) != "healthy"
    )
    down_unhealthy = sum(
        1 for n in ctx.downstream
        if normalize_health(neighbor_health.get(n, "healthy")) != "healthy"
    )

    if up_unhealthy == 0 and down_unhealthy == 0:
        return AnomalyKind.ISOLATED
    if up_unhealthy > 0 and down_unhealthy == 0:
        return AnomalyKind.UPSTREAM
    if up_unhealthy == 0 and down_unhealthy > 0:
        return AnomalyKind.CASCADING
    return AnomalyKind.CASCADING


# ─────────────────────────────────────────────────────────────────────
# Convenience for callers
# ─────────────────────────────────────────────────────────────────────
def describe(kind: str) -> str:
    return {
        AnomalyKind.NORMAL:    "No anomaly detected.",
        AnomalyKind.ISOLATED:  "Single-service incident. No neighbor impact.",
        AnomalyKind.UPSTREAM:  "Upstream dependency unhealthy. Root cause likely upstream.",
        AnomalyKind.CASCADING: "Downstream consumers affected. Anomaly is propagating.",
    }.get(kind, "Unknown.")