"""
AnomalyContext — the object every rule is evaluated against.

Built once per anomaly by ContextBuilder.build(anomaly).

Fields available to rules (via dotted metric paths in `when` blocks):

    anomaly.id, anomaly.service_id, anomaly.score, anomaly.severity,
    anomaly.confidence, anomaly.metric, anomaly.actual_value,
    anomaly.expected_value, anomaly.deviation_sigma, anomaly.detected_at

    service.id, service.name, service.layer, service.team,
    service.runtime, service.health, service.criticality

    infra.*        ← from /api/infra/{sid} (flattened, see _flatten_infra)
    app.*          ← from /api/app/{sid}   (flattened, see _flatten_app)

    graph.upstream       → list[str]   (services this service calls)
    graph.downstream     → list[str]   (services that call this service)
    graph.upstream_healthy_count
    graph.downstream_healthy_count
    graph.neighbor_anomaly_count

    blast_radius.size, blast_radius.factor, blast_radius.members
    centrality         → float in [1, 2]

    classification.is_isolated   → bool
    classification.is_cascade    → bool
    classification.is_upstream   → bool
    classification.kind          → "NORMAL" | "ISOLATED" | "UPSTREAM" | "CASCADING"
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.graph_store import GraphStore
from app.core.centrality import CentralityCalculator
from app.core.blast_radius import BlastRadiusAnalyzer

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Health normalization: mock uses "failing", graph uses "down"
# ─────────────────────────────────────────────────────────────────────
_HEALTH_ALIASES = {
    "healthy": "healthy",
    "ok": "healthy",
    "degraded": "degraded",
    "warn": "degraded",
    "warning": "degraded",
    "failing": "down",
    "down": "down",
    "critical": "down",
}


def normalize_health(raw: str | None) -> str:
    if not raw:
        return "healthy"
    return _HEALTH_ALIASES.get(str(raw).lower(), "healthy")


# ─────────────────────────────────────────────────────────────────────
# Flatteners — turn nested telemetry dicts into dotted metric paths
# ─────────────────────────────────────────────────────────────────────
def _flatten_infra(infra: dict[str, Any] | None) -> dict[str, Any]:
    """infra.cpu.usage_pct, infra.memory.pct, infra.uptime_seconds, ..."""
    if not infra:
        return {}
    out: dict[str, Any] = {}
    for k, v in infra.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                out[f"{k}.{k2}"] = v2
        else:
            out[k] = v
    return out


def _flatten_app(app: dict[str, Any] | None) -> dict[str, Any]:
    """app.latency_ms.p99, app.error_rate, app.saturation_pct, ..."""
    if not app:
        return {}
    out: dict[str, Any] = {}
    for k, v in app.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                out[f"{k}.{k2}"] = v2
        else:
            out[k] = v
    return out


# ─────────────────────────────────────────────────────────────────────
# The Context itself
# ─────────────────────────────────────────────────────────────────────
@dataclass
class AnomalyContext:
    # raw inputs
    anomaly: dict[str, Any]
    service: dict[str, Any]           # from mock SERVICES[sid]
    infra: dict[str, Any] = field(default_factory=dict)
    app: dict[str, Any] = field(default_factory=dict)

    # graph shape (populated by builder)
    upstream: list[str] = field(default_factory=list)
    downstream: list[str] = field(default_factory=list)

    # graph health (populated by builder)
    upstream_healthy_count: int = 0
    downstream_healthy_count: int = 0
    neighbor_anomaly_count: int = 0
    recent_service_anomaly_count: int = 0

    # graph metrics
    centrality: float = 1.0
    blast_size: int = 0
    blast_factor: float = 1.0
    blast_members: list[str] = field(default_factory=list)

    # classification (set by classifier)
    kind: str = "NORMAL"              # NORMAL | ISOLATED | UPSTREAM | CASCADING

    # bookkeeping
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── derived views ─────────────────────────────────────────────
    @property
    def is_isolated(self) -> bool:
        return self.kind == "ISOLATED"

    @property
    def is_upstream(self) -> bool:
        return self.kind == "UPSTREAM"

    @property
    def is_cascade(self) -> bool:
        return self.kind == "CASCADING"

    @property
    def service_id(self) -> str:
        return self.service.get("service_id") or self.anomaly.get("service_id", "")

    @property
    def service_health(self) -> str:
        """Normalized health from service catalog OR graph."""
        raw = self.service.get("health") or self.service.get("status")
        if not raw:
            # fall back to graph node
            g = GraphStore().graph()
            if self.service_id in g:
                raw = g.nodes[self.service_id].get("health")
        return normalize_health(raw)

    # ── the metric-path resolver used by the condition evaluator ──
    def resolve(self, path: str) -> Any:
        """
        Resolve a dotted path like 'anomaly.score' or 'infra.cpu.usage_pct'
        or 'graph.downstream' into an actual value.

        Returns None if any segment is missing.
        """
        root, _, rest = path.partition(".")

        # ── top-level namespaces ─────────────────────────────────
        if root == "anomaly":
            return _dig(self.anomaly, rest)
        if root == "service":
            if rest == "id":
                return self.service_id
            if rest == "health":
                return self.service_health
            return _dig(self.service, rest)
        if root == "infra":
            return _dig(_flatten_infra(self.infra), rest)
        if root == "app":
            return _dig(_flatten_app(self.app), rest)
        if root == "centrality":
            return self.centrality
        if root == "blast_radius":
            if rest == "size":
                return self.blast_size
            if rest == "factor":
                return self.blast_factor
            if rest == "members":
                return self.blast_members
            return None
        if root == "classification":
            if rest == "kind":
                return self.kind
            if rest == "is_isolated":
                return self.is_isolated
            if rest == "is_cascade":
                return self.is_cascade
            if rest == "is_upstream":
                return self.is_upstream
            return None
        if root == "graph":
            if rest == "upstream":
                return self.upstream
            if rest == "downstream":
                return self.downstream
            if rest == "upstream_healthy_count":
                return self.upstream_healthy_count
            if rest == "downstream_healthy_count":
                return self.downstream_healthy_count
            if rest == "neighbor_anomaly_count":
                return self.neighbor_anomaly_count
            return None

        # unknown namespace → None
        return None

    # ── for logging / debugging / decision_log.context JSONB ──────
    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly": self.anomaly,
            "service_id": self.service_id,
            "service_layer": self.service.get("layer"),
            "service_team": self.service.get("team"),
            "service_health": self.service_health,
            "upstream": self.upstream,
            "downstream": self.downstream,
            "upstream_healthy_count": self.upstream_healthy_count,
            "downstream_healthy_count": self.downstream_healthy_count,
            "neighbor_anomaly_count": self.neighbor_anomaly_count,
            "recent_service_anomaly_count": self.recent_service_anomaly_count,
            "centrality": self.centrality,
            "blast_size": self.blast_size,
            "blast_factor": self.blast_factor,
            "blast_members": self.blast_members,
            "kind": self.kind,
        }


def _dig(d: dict[str, Any], dotted: str) -> Any:
    """Walk a dotted path into a dict. Returns None on any miss."""
    if not dotted:
        return d
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


# ─────────────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────────────
class ContextBuilder:
    """Builds an AnomalyContext from an anomaly dict + telemetry."""

    def __init__(
        self,
        centrality: CentralityCalculator | None = None,
        blast: BlastRadiusAnalyzer | None = None,
        services_catalog: dict[str, dict] | None = None,
    ):
        self.store = GraphStore()
        self.centrality_calc = centrality or CentralityCalculator(self.store)
        self.blast_calc = blast or BlastRadiusAnalyzer(self.store)
        self._services = services_catalog or {}

    def set_services_catalog(self, catalog: dict[str, dict]) -> None:
        """Injected at startup with mock_data.SERVICES (or real catalog later)."""
        self._services = catalog

    def build(
        self,
        anomaly: dict[str, Any],
        infra: dict[str, Any] | None = None,
        app: dict[str, Any] | None = None,
        recent_anomalies: list[dict[str, Any]] | None = None,
    ) -> AnomalyContext:
        sid = anomaly.get("service_id", "")
        g = self.store.graph()

        # ── graph neighbors ──────────────────────────────────────
        upstream: list[str] = []
        downstream: list[str] = []
        if sid in g:
            upstream = list(g.successors(sid))       # what sid calls
            downstream = list(g.predecessors(sid))   # what calls sid

        # ── neighbor health ──────────────────────────────────────
        up_healthy = sum(
            1 for n in upstream if normalize_health(self._node_health(n)) == "healthy"
        )
        down_healthy = sum(
            1 for n in downstream if normalize_health(self._node_health(n)) == "healthy"
        )

        # ── neighbor anomaly count (from recent anomalies list) ──
        recent = recent_anomalies or []
        recent_ids = {a.get("service_id") for a in recent}
        neighbor_ids = set(upstream) | set(downstream)
        neighbor_anomaly_count = len(neighbor_ids & recent_ids)
        recent_service_anomaly_count = sum(
            1 for a in recent if a.get("service_id") == sid
        )

        # ── centrality + blast radius ────────────────────────────
        cent_map = self.centrality_calc.compute()
        centrality = float(cent_map.get(sid, 1.0))

        blast_size = self.blast_calc.size(sid)
        blast_factor = self.blast_calc.factor(sid)
        blast_members = sorted(self.blast_calc.reverse_reachable(sid))

        # ── service catalog entry ────────────────────────────────
        service_entry = dict(self._services.get(sid, {}))
        service_entry.setdefault("service_id", sid)
        # If catalog lacks health, pull from graph node
        if "health" not in service_entry:
            service_entry["health"] = self._node_health(sid)

        return AnomalyContext(
            anomaly=anomaly,
            service=service_entry,
            infra=infra or {},
            app=app or {},
            upstream=upstream,
            downstream=downstream,
            upstream_healthy_count=up_healthy,
            downstream_healthy_count=down_healthy,
            neighbor_anomaly_count=neighbor_anomaly_count,
            recent_service_anomaly_count=recent_service_anomaly_count,
            centrality=centrality,
            blast_size=blast_size,
            blast_factor=blast_factor,
            blast_members=blast_members,
        )

    def _node_health(self, sid: str) -> str:
        g = self.store.graph()
        if sid in g:
            return g.nodes[sid].get("health", "healthy")
        return "healthy"