"""
Decision persistence — convert Rule Engine output ↔ decision_log rows.

This is the "glue" between the in-memory pipeline and Postgres.
The Validation Layer (next module) will call persist_decision() as its
final step. Until then, you can call it manually for testing.
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from app.decision.models import Decision, SeverityBreakdown
from app.decision.severity import compute_severity
from app.decision.action_selector import select_action
from app.persistence.postgres import postgres_store
from app.rules.context import AnomalyContext
from app.rules.models import RuleCandidate

log = logging.getLogger(__name__)


def make_decision_id() -> str:
    """Generate a sortable, unique decision ID: DEC-YYYYMMDD-HHMMSS-xxxx."""
    now = datetime.now(timezone.utc)
    return f"DEC-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def build_decision(
    ctx: AnomalyContext,
    candidates: list[RuleCandidate],
) -> Decision | None:
    """
    Compose a Decision from context + candidates:
      • Severity computed
      • Action selected
      • All extra data packed into `context` JSONB
    Returns None if there are no candidates.
    """
    if not candidates:
        return None

    # ── severity ─────────────────────────────────────────────────
    sev = compute_severity(ctx.anomaly, ctx.centrality, ctx.blast_factor)

    # ── action selection ─────────────────────────────────────────
    selection = select_action(candidates)
    if selection is None:
        return None

    sel = selection.selected  # dict

    # ── build the full Decision ──────────────────────────────────
    return Decision(
        decision_id=make_decision_id(),
        anomaly_id=str(ctx.anomaly.get("id", "")),
        service_id=ctx.service_id,
        rule_id=str(sel["rule_id"]),
        rule_version=int(sel.get("rule_version", 1)),
        action=sel["action"],
        action_params=sel.get("params") or {},
        detection_conf=float(sel.get("detection_confidence", 0.0)),
        rule_conf=float(sel.get("base_confidence", 0.0)),
        final_conf=float(sel.get("final_confidence", 0.0)),
        severity=sev,
        base_risk=sel.get("base_risk", "MEDIUM"),
        blast_factor=ctx.blast_factor,
        centrality=ctx.centrality,
        guardrails=sel.get("guardrails") or {},
        selection=selection,
        service_health=ctx.service_health,
        anomaly_kind=ctx.kind,
        upstream=list(ctx.upstream),
        downstream=list(ctx.downstream),
        blast_members=list(ctx.blast_members),
        # policy_outcome + policy_reason are null — Validation Layer fills them.
    )


async def persist_decision(decision: Decision) -> bool:
    """
    Save a Decision to decision_log. Idempotent (uses ON CONFLICT DO NOTHING).

    Returns True if inserted, False otherwise.
    """
    row = decision.to_log_row()

    # The column is NOT NULL — fill with a marker so we can distinguish
    # "saved before validation" from real outcomes later.
    if row["policy_outcome"] is None:
        row["policy_outcome"] = "UNVALIDATED"
        row["policy_reason"] = "validation_layer_not_implemented"

    ok = await postgres_store.save_decision(row)
    if ok:
        log.info(
            "Decision saved: %s (%s → %s, severity=%.2f, %s)",
            row["id"], decision.service_id, decision.action.value,
            decision.severity.effective_severity, row["policy_outcome"],
        )
    else:
        log.warning("Decision NOT saved: %s", row["id"])
    return ok


def row_to_decision(row: dict[str, Any]) -> dict[str, Any]:
    """Reverse — turn a DB row into a JSON-friendly dict for the API."""
    ctx = row.get("context") or {}
    if isinstance(ctx, str):
        ctx = json.loads(ctx)

    action_params = row.get("action_params") or {}
    if isinstance(action_params, str):
        action_params = json.loads(action_params)

    return {
        "decision_id": row["id"],
        "anomaly_id": row["anomaly_id"],
        "service_id": row["service_id"],
        "rule_id": row["rule_id"],
        "rule_version": row["rule_version"],
        "action": row["action"],
        "action_params": action_params,
        "confidence": {
            "detection": row["detection_conf"],
            "rule": row["rule_conf"],
            "final": row["final_conf"],
        },
        "severity": ctx.get("severity", {
            "effective_severity": row["effective_severity"],
        }),
        "base_risk": row["base_risk"],
        "blast_factor": row["blast_factor"],
        "centrality": row["centrality"],
        "selection": ctx.get("selection", {}),
        "context": {
            "service_health": ctx.get("service_health"),
            "anomaly_kind": ctx.get("anomaly_kind"),
            "upstream": ctx.get("upstream", []),
            "downstream": ctx.get("downstream", []),
            "blast_members": ctx.get("blast_members", []),
        },
        "policy": {
            "outcome": row["policy_outcome"],
            "reason": row["policy_reason"],
        },
        "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"],
    }