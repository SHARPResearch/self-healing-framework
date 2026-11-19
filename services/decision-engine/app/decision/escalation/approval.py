# services/decision-engine/app/decision/escalation/approval.py
"""
Execute a decision that a human approved.

`queue.ack()` records the operator's verdict and stops the email schedule — by
design it does not act on it, because HUMAN_LOOP means "do not execute without
a human". Once the human says APPROVED, *something* has to translate that
verdict into the action. That is this module.

It re-reads the decision row (the escalation only stores `decision_id`, and the
row is the source of truth), runs the very same executor the AUTO_EXECUTE path
uses, and writes the same `execution_log` + `action_history` rows — so an
approved recovery is indistinguishable, downstream, from an automatic one.
That is what the audit trail should show: the action happened, and the reason
it happened was a human, which lives on the escalation row.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.decision.models import (
    ActionSelection,
    Decision,
    PolicyOutcome,
    SeverityBreakdown,
)
from app.rules.models import ActionType, RiskLevel

log = logging.getLogger(__name__)

# Result status -> the vocabulary action_history expects.
_OUTCOME_MAP = {
    "SUCCESS": "SUCCESS",
    "FAILED": "FAILED",
    "DRY_RUN": "NEUTRAL",
    "SKIPPED": "NEUTRAL",
    "NOT_IMPLEMENTED": "NEUTRAL",
}


def _json(value: Any, fallback: Any) -> Any:
    """JSONB columns come back as text; decode defensively."""
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:  # noqa: BLE001
            return fallback
    return value


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(high, max(low, number))


def _decision_from_row(row: dict) -> Decision:
    """
    Rebuild the Decision the executor needs from the persisted row.

    Only the fields an executor reads are meaningful here (action, params,
    service, id); the rest are filled from the row so the object is valid.
    """
    context = _json(row.get("context"), {}) or {}
    severity_ctx = context.get("severity") or {}
    effective = _clamp(row.get("effective_severity"), 0.0, 2.7, 0.0)
    centrality = _clamp(row.get("centrality"), 1.0, 2.0, 1.0)
    blast = _clamp(row.get("blast_factor"), 1.0, 1.5, 1.0)

    try:
        base_risk = RiskLevel(row.get("base_risk") or "MEDIUM")
    except ValueError:
        base_risk = RiskLevel.MEDIUM

    return Decision(
        decision_id=row["id"],
        anomaly_id=row["anomaly_id"],
        service_id=row["service_id"],
        rule_id=row.get("rule_id") or "operator_override",
        rule_version=int(row.get("rule_version") or 1),
        action=ActionType(row["action"]),
        action_params=_json(row.get("action_params"), {}) or {},
        detection_conf=_clamp(row.get("detection_conf"), 0.0, 1.0, 0.0),
        rule_conf=_clamp(row.get("rule_conf"), 0.0, 1.0, 0.0),
        final_conf=_clamp(row.get("final_conf"), 0.0, 1.0, 0.0),
        severity=SeverityBreakdown(
            base_severity=_clamp(severity_ctx.get("base_severity"), 0.0, 1.0, 0.9),
            centrality=centrality,
            blast_factor=blast,
            effective_severity=effective,
            normalized=min(1.0, effective / 2.7),
            label=str(severity_ctx.get("label") or "UNKNOWN"),
        ),
        base_risk=base_risk,
        blast_factor=blast,
        centrality=centrality,
        selection=ActionSelection(
            selected={},
            rejected=[],
            strategy="operator_approved",
            reason="executed because an operator approved the escalation",
        ),
        # The executor records this in execution_log; the decision row keeps
        # HUMAN_LOOP so the original routing stays visible in the audit trail.
        policy_outcome=PolicyOutcome.AUTO_EXECUTE,
        policy_reason="approved by operator via escalation",
    )


async def execute_approved(decision_id: str) -> dict[str, Any]:
    """
    Run the executor for a decision a human approved.

    Returns a JSON-safe summary that the caller stores inside the escalation's
    `response` field, so the UI can show what the approval actually did.
    """
    from app.decision.executor import get_executor
    from app.persistence.postgres import postgres_store

    row = await postgres_store.get_decision(decision_id)
    if not row:
        log.error("approval: decision %s not found — cannot execute", decision_id)
        return {
            "status": "NOT_FOUND",
            "message": f"decision {decision_id} no longer exists",
        }

    try:
        decision = _decision_from_row(row)
    except Exception as exc:  # noqa: BLE001
        log.exception("approval: could not rebuild decision %s", decision_id)
        return {"status": "FAILED", "message": f"could not rebuild decision: {exc}"}

    try:
        # get_executor() honours KUBERNETES_DRY_RUN, exactly like the pipeline.
        result = await get_executor().execute(decision)
    except Exception as exc:  # noqa: BLE001
        log.exception("approval: executor raised for %s", decision_id)
        return {"status": "FAILED", "message": f"executor raised: {exc}"}

    payload = result.to_dict()

    try:
        await postgres_store.save_execution(payload)
    except Exception:  # noqa: BLE001
        log.exception("approval: save_execution failed for %s", decision_id)

    try:
        await postgres_store.record_action_outcome(
            decision_id=decision_id,
            service_id=row["service_id"],
            action=payload["action"],
            outcome=_OUTCOME_MAP.get(payload["status"], "UNKNOWN"),
        )
    except Exception:  # noqa: BLE001
        log.exception("approval: record_action_outcome failed for %s", decision_id)

    log.info(
        "approval: executed %s → %s status=%s (%s)",
        decision_id, payload["action"], payload["status"], payload["message"],
    )

    return {
        "status": payload["status"],
        "message": payload["message"],
        "action": payload["action"],
        "executed_at": payload["executed_at"],
    }
