# services/decision-engine/app/decision/validation/shadow.py
"""
Shadow Mode analyzer — produces the counterfactual record described in
design doc §4.4.

The JSON shape is the contract:

    {
      "SHADOW_ID": "...",
      "SERVICE": "payment-svc",
      "ANOMALY_SCORE": 0.72,
      "CANDIDATE_ACTION": "RESTART_POD",
      "CONFIDENCE": 0.71,
      "RISK": "MEDIUM",
      "POLICY_OUTCOME": "SHADOW_MODE",
      "SIMULATED_OUTCOME": {"EXPECTED_ANOMALY_DROP": ..., "EXPECTED_RECOVERY_TIME_SEC": ...},
      "ACTUAL_OUTCOME": null,           # filled when the anomaly later resolves
      "VERDICT": null,                  # filled when ACTUAL_OUTCOME is set
      "LEARNING": null
    }

This module produces the *initial* row — everything up to ACTUAL_OUTCOME.
The verdict (would the action have helped?) is produced later by an
`observe_shadow_outcome()` function that we run in a background job.

The `simulated_outcome` estimate is deliberately simple: a lookup table
keyed by action type. The real simulator (when we build Component 3's
RL environment) will replace it. Keeping a table now means the field is
never null and downstream tooling can rely on it.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from app.decision.validation.result import ConfidenceBreakdown
from app.rules.context import AnomalyContext
from app.rules.models import ActionType, RiskLevel


# ─────────────────────────────────────────────────────────────────────
# Simple simulation table — pre-RL placeholder.
# Values are (expected_anomaly_drop, expected_recovery_time_sec).
# Conservative guesses from operational experience.
# ─────────────────────────────────────────────────────────────────────
_SIM: dict[ActionType, tuple[float, int]] = {
    ActionType.RESTART_POD:       (0.35, 45),
    ActionType.SCALE_UP:          (0.30, 30),
    ActionType.SCALE_DOWN:        (0.10, 60),
    ActionType.ROLLBACK:          (0.45, 90),
    ActionType.OPEN_CIRCUIT:      (0.25, 15),
    ActionType.CLOSE_CIRCUIT:     (0.20, 20),
    ActionType.FLUSH_CACHE:       (0.30, 10),
    ActionType.INCREASE_DB_POOL:  (0.25, 25),
    ActionType.SCALE_CONSUMERS:   (0.20, 30),
    ActionType.DRAIN_NODE:        (0.15, 120),
    ActionType.NOOP:              (0.00, 0),
}


def make_shadow_id() -> str:
    now = datetime.now(timezone.utc)
    return f"SHD-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def build_shadow_payload(
    *,
    decision_id: str,
    anomaly_id: str,
    ctx: AnomalyContext,
    action: ActionType,
    confidence: ConfidenceBreakdown,
    risk: RiskLevel,
) -> dict[str, Any]:
    """
    Return the dict that becomes one row in `shadow_records`
    (and, in the API, `decision_log.context.shadow`).
    """
    drop, recovery_sec = _SIM.get(action, (0.20, 60))

    return {
        "SHADOW_ID": make_shadow_id(),
        "DECISION_ID": decision_id,
        "ANOMALY_ID": anomaly_id,
        "SERVICE": ctx.service_id,
        "ANOMALY_SCORE": float(ctx.anomaly.get("anomaly_score", 0.0)),
        "CANDIDATE_ACTION": action.value,
        "CONFIDENCE": round(confidence.effective, 4),
        "RISK": risk.value,
        "POLICY_OUTCOME": "SHADOW_MODE",
        "SIMULATED_OUTCOME": {
            "EXPECTED_ANOMALY_DROP": drop,
            "EXPECTED_RECOVERY_TIME_SEC": recovery_sec,
        },
        "ACTUAL_OUTCOME": None,
        "VERDICT": None,
        "LEARNING": None,
    }


def observe_shadow_outcome(
    shadow_row: dict[str, Any],
    *,
    resolved_naturally: bool,
    resolution_time_sec: int,
) -> dict[str, Any]:
    """
    Fill in the ACTUAL_OUTCOME / VERDICT / LEARNING of an existing
    shadow row. Called by a background observer once the anomaly
    resolves (naturally or via escalation).

    Returns the mutated copy (caller persists).
    """
    row = dict(shadow_row)
    row["ACTUAL_OUTCOME"] = {
        "ANOMALY_RESOLVED_NATURALLY": bool(resolved_naturally),
        "RESOLUTION_TIME_SEC": int(resolution_time_sec),
    }

    expected = row.get("SIMULATED_OUTCOME") or {}
    expected_drop = float(expected.get("EXPECTED_ANOMALY_DROP", 0.0))
    expected_sec = int(expected.get("EXPECTED_RECOVERY_TIME_SEC", 0))

    # Verdict logic (design doc §4.4 example):
    #   * resolved naturally in <= expected_sec + 50%  → unnecessary
    #   * would have helped but never executed          → helpful_but_missed
    #   * anomaly did not resolve                       → would_have_helped
    if resolved_naturally and resolution_time_sec <= expected_sec * 1.5:
        verdict = "ACTION_WOULD_HAVE_BEEN_UNNECESSARY"
        learning = (
            f"reduce weight of {row.get('CANDIDATE_ACTION')} rule "
            f"for {row.get('SERVICE')}"
        )
    elif resolved_naturally:
        verdict = "ACTION_WOULD_HAVE_HELPED"
        learning = "shadow action likely would have shortened resolution time"
    else:
        verdict = "ACTION_WOULD_HAVE_HELPED"
        learning = "incident did not self-resolve — shadow action would likely have helped"

    row["VERDICT"] = verdict
    row["LEARNING"] = learning
    return row