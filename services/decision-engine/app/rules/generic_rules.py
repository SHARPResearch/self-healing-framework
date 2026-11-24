# services/decision-engine/app/rules/generic_rules.py
"""
Service-agnostic recovery rules.

The original seed rules were written against one specific service catalog
(`api-gateway`, `orders-service`, `redis-cache`, …) and scoped by layer, so on
any other project — the Online Boutique cluster, a different demo, someone
else's microservices — nothing matched and every anomaly became
`NO_RULE_MATCHED`.

These rules depend only on context that exists for *every* anomaly:

    anomaly.score / anomaly.severity   from the detector
    classification.is_isolated / is_cascade / is_upstream
    blast_radius.factor / blast_radius.size
    service.health

No metric names, no service lists, no layer filters — so they fire on any
microservice fleet. They are appended to the default set by
`RuleRegistry.seed_if_empty()`, which is idempotent per id, so an existing
deployment picks them up on its next restart without touching operator edits.

Deliberately spread across the four policy outcomes so a demo can show each
branch of the policy matrix:

    generic_restart_isolated  → AUTO_EXECUTE   (0.90 confidence, LOW risk)
    generic_cascading_scale   → SHADOW_MODE    (0.80, MEDIUM)
    generic_upstream_fallback → SHADOW_MODE    (0.72, MEDIUM)
    generic_high_blast_scale  → HUMAN_LOOP     (HIGH risk)
    generic_down_restart      → SHADOW_MODE    (0.78, MEDIUM)
"""
from __future__ import annotations

# Guardrail defaults shared by the generic rules. Short enough for a demo,
# long enough that a chaotic cluster cannot be restarted in a loop.
_COOLDOWN_SEC = 180
_MAX_PER_HOUR = 3


def _rule(
    rule_id: str,
    priority: int,
    description: str,
    when: dict,
    action: str,
    params: dict,
    confidence: float,
    risk: str,
    tags: list[str],
    idem: str,
) -> dict:
    return {
        "id": rule_id,
        "version": 1,
        "priority": priority,
        "description": description,
        "enabled": True,
        "is_default": True,
        # Empty layers + "*" services = every service in every project.
        "applies_to": {"layers": [], "services": ["*"], "exclude_services": []},
        "when": when,
        "then": {
            "action": action,
            "params": params,
            "base_confidence": confidence,
            "base_risk": risk,
        },
        "guardrails": {
            "cooldown_seconds": _COOLDOWN_SEC,
            "max_per_hour": _MAX_PER_HOUR,
            "idempotency_key": idem,
        },
        "tags": tags,
    }


_K8S_PARAMS = {
    "namespace": "{{ service.namespace }}",
    "selector": "app={{ service.id }}",
    "grace_period_seconds": 30,
}

GENERIC_RULES: list[dict] = [
    # ── 1. Isolated high-severity anomaly → restart the pod ──────────
    _rule(
        "generic_restart_isolated",
        130,
        "Isolated high-score anomaly: restart the affected pod (any service)",
        {
            "all": [
                {"metric": "classification.is_isolated", "op": "==", "value": True},
                {"metric": "anomaly.score", "op": ">=", "value": 0.85},
            ]
        },
        "RESTART_POD",
        _K8S_PARAMS,
        0.90,
        "LOW",
        ["isolated", "restart", "generic"],
        "generic-restart:{{ service.id }}:{{ anomaly.id }}",
    ),

    # ── 2. Cascading risk → pre-scale every affected member ──────────
    _rule(
        "generic_cascading_scale",
        125,
        "Cascading anomaly across dependent services: scale out, do not restart",
        {
            "all": [
                {"metric": "classification.is_cascade", "op": "==", "value": True},
                {"metric": "anomaly.score", "op": ">=", "value": 0.70},
            ]
        },
        "SCALE_UP",
        {
            "namespace": "{{ service.namespace }}",
            "selector": "app={{ service.id }}",
            "replicas": 2,
        },
        0.80,
        "MEDIUM",
        ["cascade", "scale", "generic"],
        "generic-cascade:{{ service.id }}:{{ anomaly.id }}",
    ),

    # ── 3. Upstream propagation → fall back instead of restarting ────
    _rule(
        "generic_upstream_fallback",
        120,
        "Anomaly propagated from a dependency: open the circuit, do not restart the symptom",
        {
            "all": [
                {"metric": "classification.is_upstream", "op": "==", "value": True},
                {"metric": "anomaly.score", "op": ">=", "value": 0.65},
            ]
        },
        "OPEN_CIRCUIT",
        {"namespace": "{{ service.namespace }}", "selector": "app={{ service.id }}"},
        0.72,
        "MEDIUM",
        ["upstream", "fallback", "generic"],
        "generic-upstream:{{ service.id }}:{{ anomaly.id }}",
    ),

    # ── 4. Wide blast radius → a human decides ───────────────────────
    _rule(
        "generic_high_blast_scale",
        115,
        "High-severity anomaly on a widely depended-on service: escalate to a human",
        {
            "all": [
                {"metric": "anomaly.score", "op": ">=", "value": 0.80},
                {"metric": "blast_radius.factor", "op": ">=", "value": 1.15},
            ]
        },
        "SCALE_UP",
        {
            "namespace": "{{ service.namespace }}",
            "selector": "app={{ service.id }}",
            "replicas": 2,
        },
        0.88,
        "HIGH",
        ["blast-radius", "human", "generic"],
        "generic-blast:{{ service.id }}:{{ anomaly.id }}",
    ),

    # ── 5. Service already down → restart after the high-score gate ──
    _rule(
        "generic_down_restart",
        110,
        "Service reported down with a very high anomaly score: restart the pod",
        {
            "all": [
                {"metric": "anomaly.score", "op": ">=", "value": 0.90},
                {"metric": "service.health", "op": "in", "value": ["down", "critical"]},
            ]
        },
        "RESTART_POD",
        _K8S_PARAMS,
        0.78,
        "MEDIUM",
        ["down", "restart", "generic"],
        "generic-down:{{ service.id }}:{{ anomaly.id }}",
    ),
]
