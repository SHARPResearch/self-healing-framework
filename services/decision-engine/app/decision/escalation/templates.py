# services/decision-engine/app/decision/escalation/templates.py
"""
Email templates for the 3-attempt escalation flow (design doc §3.5.3).

Three templates, one per attempt:
    1. INITIAL          — "human validation required, please approve/reject"
    2. REMINDER         — "no response yet, warning flag"
    3. FINAL_FAILURE    — "3 attempts exhausted, manual intervention required"

Each template returns (subject, text_body, html_body). The HTML shell
reuses the branding/helpers from app.notifications.emailer, so both the
existing decision emails and the new escalation emails look identical.

Transport is unchanged: emails go through `app.notifications.emailer._send`.
"""
from __future__ import annotations

from html import escape
from typing import Any

from app.decision.escalation.queue import Escalation
from app.notifications.emailer import (   # type: ignore[attr-defined]
    _email_shell,
    _row,
    _fmt,
    _fmt_ts,
    _severity_color,
    _SYSTEM_NAME,
    _ALERT,
    _WARN,
    _OK,
)


# ─────────────────────────────────────────────────────────────────────
# Attempt 1 — INITIAL
# ─────────────────────────────────────────────────────────────────────
def initial(
    esc: Escalation,
    decision: dict[str, Any],
    anomaly: dict[str, Any] | None,
) -> tuple[str, str, str]:
    svc = (anomaly or {}).get("service_name") or esc.service_id
    action = decision.get("action") or "—"
    risk = (decision.get("base_risk") or "HIGH").upper()
    conf = _fmt((decision.get("confidence") or {}).get("final"), 3)
    sev = (decision.get("severity") or {})
    sev_label = sev.get("label") or "HIGH"
    accent = _severity_color(sev_label)

    subject = f"[SHARP] ⚠ Human approval required: {action} on {svc}"

    text = (
        f"{_SYSTEM_NAME}\n"
        f"HUMAN APPROVAL REQUIRED (attempt 1 of 3)\n"
        f"{'-' * 46}\n\n"
        f"The decision engine has selected a recovery action that\n"
        f"requires human validation before execution.\n\n"
        f"Service           : {svc} ({esc.service_id})\n"
        f"Recommended action: {action}\n"
        f"Risk level        : {risk}\n"
        f"Effective severity: {sev_label}\n"
        f"Confidence        : {conf}\n"
        f"Decision ID       : {esc.decision_id}\n"
        f"Anomaly ID        : {esc.anomaly_id}\n"
        f"Escalation ID     : {esc.id}\n\n"
        f"WHAT TO DO:\n"
        f"  Approve: POST /api/decisions/escalations/{esc.id}/ack?decision=APPROVED\n"
        f"  Reject : POST /api/decisions/escalations/{esc.id}/ack?decision=REJECTED\n\n"
        f"Without a response, this will be re-sent in 5 minutes,\n"
        f"and marked MANUAL_REQUIRED after 15 minutes.\n"
    )

    html = _email_shell(
        title="Human approval required",
        subtitle_html=(
            f"Attempt 1 of 3 · <strong>{escape(str(svc))}</strong> · "
            f"<strong>{escape(str(action))}</strong>"
        ),
        summary=(
            "The decision engine has selected a recovery action that requires "
            "human validation before execution."
        ),
        accent=accent,
        preheader=f"Approve {action} on {svc} — attempt 1 of 3.",
        rows=[
            ("Service", f"{svc} ({esc.service_id})"),
            ("Recommended action", str(action)),
            ("Risk level", str(risk)),
            ("Effective severity", str(sev_label)),
            ("Confidence", conf),
            ("Decision ID", esc.decision_id),
            ("Anomaly ID", esc.anomaly_id),
            ("Escalation ID", esc.id),
            ("Approve URL", f"POST /api/decisions/escalations/{esc.id}/ack?decision=APPROVED"),
            ("Reject URL", f"POST /api/decisions/escalations/{esc.id}/ack?decision=REJECTED"),
        ],
        footer_note="Escalation attempt 1 of 3. Reminder in 5 minutes.",
    )
    return subject, text, html


# ─────────────────────────────────────────────────────────────────────
# Attempt 2 — REMINDER
# ─────────────────────────────────────────────────────────────────────
def reminder(
    esc: Escalation,
    decision: dict[str, Any],
    anomaly: dict[str, Any] | None,
) -> tuple[str, str, str]:
    svc = (anomaly or {}).get("service_name") or esc.service_id
    action = decision.get("action") or "—"

    subject = f"[SHARP] ⚠️ REMINDER: no response for {action} on {svc}"

    text = (
        f"{_SYSTEM_NAME}\n"
        f"REMINDER — HUMAN APPROVAL STILL REQUIRED (attempt 2 of 3)\n"
        f"{'-' * 46}\n\n"
        f"No response was received for the initial escalation.\n\n"
        f"Service           : {svc} ({esc.service_id})\n"
        f"Recommended action: {action}\n"
        f"Decision ID       : {esc.decision_id}\n"
        f"Escalation ID     : {esc.id}\n\n"
        f"Approve: POST /api/decisions/escalations/{esc.id}/ack?decision=APPROVED\n"
        f"Reject : POST /api/decisions/escalations/{esc.id}/ack?decision=REJECTED\n\n"
        f"If no response in 10 minutes, this incident will be marked\n"
        f"MANUAL_REQUIRED and the final failure report will be sent.\n"
    )

    html = _email_shell(
        title="Reminder — approval still required",
        subtitle_html=(
            f"Attempt 2 of 3 · <strong>{escape(str(svc))}</strong> · "
            f"<strong>{escape(str(action))}</strong>"
        ),
        summary=(
            "No response was received for the initial escalation. "
            "Without a reply in 10 minutes, this incident will be marked "
            "MANUAL_REQUIRED."
        ),
        accent=_WARN,
        preheader=f"Reminder: approve {action} on {svc}.",
        rows=[
            ("Service", f"{svc} ({esc.service_id})"),
            ("Recommended action", str(action)),
            ("Decision ID", esc.decision_id),
            ("Escalation ID", esc.id),
            ("Approve URL", f"POST /api/decisions/escalations/{esc.id}/ack?decision=APPROVED"),
            ("Reject URL", f"POST /api/decisions/escalations/{esc.id}/ack?decision=REJECTED"),
        ],
        footer_note="Escalation attempt 2 of 3. Final report in 10 minutes.",
    )
    return subject, text, html


# ─────────────────────────────────────────────────────────────────────
# Attempt 3 — FINAL FAILURE REPORT
# ─────────────────────────────────────────────────────────────────────
def final_failure(
    esc: Escalation,
    decision: dict[str, Any],
    anomaly: dict[str, Any] | None,
) -> tuple[str, str, str]:
    svc = (anomaly or {}).get("service_name") or esc.service_id
    action = decision.get("action") or "—"

    subject = f"[SHARP] ❌ MANUAL INTERVENTION REQUIRED: {action} on {svc}"

    text = (
        f"{_SYSTEM_NAME}\n"
        f"MANUAL INTERVENTION REQUIRED — FINAL REPORT (attempt 3 of 3)\n"
        f"{'-' * 46}\n\n"
        f"All 3 escalation attempts have been exhausted with no operator\n"
        f"response. This incident is now marked MANUAL_REQUIRED.\n\n"
        f"Service           : {svc} ({esc.service_id})\n"
        f"Unresolved action : {action}\n"
        f"Decision ID       : {esc.decision_id}\n"
        f"Anomaly ID        : {esc.anomaly_id}\n"
        f"Escalation ID     : {esc.id}\n\n"
        f"RECOMMENDED MANUAL STEPS:\n"
        f"  1. Investigate the anomaly at /api/anomalies/{esc.anomaly_id}/evidence\n"
        f"  2. Confirm current service state at /api/services/{esc.service_id}\n"
        f"  3. Execute remediation manually if safe to do so\n"
        f"  4. Mark resolved via: POST /api/decisions/escalations/{esc.id}/ack\n"
    )

    html = _email_shell(
        title="Manual intervention required",
        subtitle_html=(
            f"Attempt 3 of 3 · <strong>{escape(str(svc))}</strong> · "
            f"<strong>{escape(str(action))}</strong>"
        ),
        summary=(
            "All 3 escalation attempts have been exhausted. This incident is "
            "now marked MANUAL_REQUIRED and requires operator investigation."
        ),
        accent=_ALERT,
        preheader=f"MANUAL REQUIRED: {action} on {svc} after 3 attempts.",
        rows=[
            ("Service", f"{svc} ({esc.service_id})"),
            ("Unresolved action", str(action)),
            ("Decision ID", esc.decision_id),
            ("Anomaly ID", esc.anomaly_id),
            ("Escalation ID", esc.id),
            ("Evidence URL", f"GET /api/anomalies/{esc.anomaly_id}/evidence"),
            ("Acknowledge", f"POST /api/decisions/escalations/{esc.id}/ack"),
        ],
        footer_note="Final escalation attempt. Manual intervention required.",
    )
    return subject, text, html