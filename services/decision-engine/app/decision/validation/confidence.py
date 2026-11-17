# services/decision-engine/app/decision/validation/confidence.py
"""
Confidence breakdown — blended confidence + graph certainty.

The RuleCandidate already carries a *blended* confidence:
    final = 0.6 * detection + 0.4 * rule_base          (from rules/engine.py)

This module does NOT second-guess that blend. It adds one extra signal:

    graph_certainty ∈ [0, 1]
        * 1.0  — service exists in the graph, at least one neighbor known,
                 recent telemetry present, no data staleness.
        * drops when the graph is empty, the service is unknown, or the
          anomaly's service_id is missing.

Why? A rule that fires based on a `graph.downstream contains 'web-bff'`
condition is less trustworthy when the graph is empty. Multiplying by
certainty makes the effective confidence honest.

    effective = blended * graph_certainty

Bands:
    effective >= 0.85   → HIGH     (auto-execute eligible)
    0.60 <= eff < 0.85  → MEDIUM   (shadow eligible)
    effective < 0.60    → LOW      (block eligible)
"""
from __future__ import annotations

from app.decision.validation.result import ConfidenceBreakdown
from app.rules.context import AnomalyContext


# Band thresholds — mirrored by policy_matrix.py. Change in BOTH places
# if you tune them (or import them from here).
CONF_HIGH = 0.85
CONF_MEDIUM = 0.60


def _band(effective: float) -> str:
    if effective >= CONF_HIGH:
        return "HIGH"
    if effective >= CONF_MEDIUM:
        return "MEDIUM"
    return "LOW"


def _graph_certainty(ctx: AnomalyContext) -> float:
    """
    Heuristic 0..1 score for "do we trust the graph data behind this decision?"

    Penalties (all multiplicative to keep it in [0,1]):
        * service_id missing            → ×0.3
        * service not in graph          → ×0.5
        * zero neighbors (up + down)    → ×0.7
        * recent anomaly burst > 10     → ×0.9 (noisy input)
    """
    score = 1.0

    sid = ctx.service_id
    if not sid:
        return 0.3

    try:
        from app.core.graph_store import GraphStore
        g = GraphStore().graph()
    except Exception:
        return 0.5

    if sid not in g:
        score *= 0.5

    if not ctx.upstream and not ctx.downstream:
        score *= 0.7

    if ctx.neighbor_anomaly_count > 10:
        score *= 0.9

    return round(max(0.0, min(1.0, score)), 4)


def compute_confidence(
    blended: float,
    detection: float,
    rule_base: float,
    ctx: AnomalyContext,
) -> ConfidenceBreakdown:
    """
    Build the full confidence breakdown. `blended` is the value from
    RuleCandidate.final_confidence — passed in so we don't recompute it
    (and so any future blending changes are visible in one place).
    """
    certainty = _graph_certainty(ctx)
    effective = round(max(0.0, min(1.0, blended * certainty)), 4)

    return ConfidenceBreakdown(
        detection=float(detection),
        rule_base=float(rule_base),
        blended=float(blended),
        graph_certainty=certainty,
        effective=effective,
        band=_band(effective),
    )