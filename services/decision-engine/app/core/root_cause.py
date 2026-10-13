"""
Root Cause Localizer.

Given N anomalies in a time window, find the ONE service that is the
source of the cascade.

Algorithm:
    1. Sort anomalies by detected_at (earliest first)
    2. If only one anomaly → it IS the root
    3. For each anomaly, compute:
         - upstream_healthy:  all upstream neighbors are healthy?
         - downstream_affected: at least one downstream neighbor has an anomaly?
    4. The service with upstream_healthy=True AND downstream_affected=True
       is a strong root candidate.
    5. If multiple, pick the one with:
         - earliest detected_at (breaks ties in cascades)
         - largest blast radius (more downstream impact)
         - higher criticality

Fallbacks:
    - If no clear root, walk backwards from all anomalies to find the
      deepest common ancestor in the graph.
    - If still none, return the earliest anomaly.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.graph_store import GraphStore

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────
def localize_root_cause(
    anomalies: list[dict[str, Any]],
    window_sec: int = 60,
    graph: GraphStore | None = None,
) -> str | None:
    """
    Return the service_id of the root cause, or None if anomalies is empty.

    `anomalies` items must have at least:
        { "service_id": str, "detected_at": ISO string or datetime }
    and may have:
        { "anomaly_score": float, "severity": str }
    """
    if not anomalies:
        return None
    if len(anomalies) == 1:
        return anomalies[0].get("service_id")

    store = graph or GraphStore()
    g = store.graph()

    # ── 1. Sort earliest first ───────────────────────────────────
    sorted_a = sorted(anomalies, key=lambda a: _ts(a.get("detected_at")))

    # ── 2. Restrict to time window (from earliest) ───────────────
    t0 = _ts(sorted_a[0].get("detected_at"))
    in_window = [
        a for a in sorted_a
        if (_ts(a.get("detected_at")) - t0).total_seconds() <= window_sec
    ]

    # ── 3. Build sets ────────────────────────────────────────────
    affected_sids = {a.get("service_id") for a in in_window if a.get("service_id")}

    # ── 4. Score each candidate ──────────────────────────────────
    candidates: list[tuple[str, float, float, datetime]] = []
    for a in in_window:
        sid = a.get("service_id")
        if not sid or sid not in g:
            continue

        upstream = set(g.successors(sid))       # what sid calls
        downstream = set(g.predecessors(sid))   # who calls sid

        upstream_affected = upstream & affected_sids
        downstream_affected = downstream & affected_sids

        # Strong root: upstream healthy, downstream affected
        if not upstream_affected and downstream_affected:
            score = _root_score(sid, downstream_affected, g)
            candidates.append((sid, score, 2.0, _ts(a.get("detected_at"))))

        # Leaf that is only up: could still be root (no neighbors affected)
        elif not upstream_affected and not downstream_affected:
            # Single-isolated case; low priority
            candidates.append((sid, 0.5, 1.0, _ts(a.get("detected_at"))))

        # If downstream AND upstream both affected → likely a middleman
        # Do NOT promote as root.
        else:
            candidates.append((sid, 0.2, 0.5, _ts(a.get("detected_at"))))

    # ── 5. Pick best ─────────────────────────────────────────────
    if candidates:
        # Sort by: weight DESC, score DESC, earliest timestamp ASC
        candidates.sort(key=lambda c: (-c[2], -c[1], c[3]))
        best = candidates[0]
        log.info(
            "Root cause localized: %s (score=%.2f, weight=%.1f, %d candidates)",
            best[0], best[1], best[2], len(candidates),
        )
        return best[0]

    # ── 6. Fallback: earliest anomaly ────────────────────────────
    log.info("No strong root found; falling back to earliest anomaly")
    return sorted_a[0].get("service_id")


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _root_score(sid: str, downstream_affected: set[str], g) -> float:
    """
    Higher = better root candidate.
    Factors: number of affected downstream, criticality, graph degree.
    """
    try:
        crit = float(g.nodes[sid].get("criticality", 1.0))
    except Exception:
        crit = 1.0
    return len(downstream_affected) * crit


def _ts(v: Any) -> datetime:
    if v is None:
        return datetime.now(timezone.utc)
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)