# services/decision-engine/app/decision/escalation/worker.py
"""
Escalation worker — fires attempts on schedule.

Runs on APScheduler every 30s (configurable via ESCALATION_POLL_INTERVAL_SEC).
For each escalation where next_attempt_at <= now:

    attempt 1 → templates.initial()
    attempt 2 → templates.reminder()
    attempt 3 → templates.final_failure()

Then `record_attempt()` updates state and schedules the next attempt.

Delivery reuses `app.notifications.emailer._send()` so escalation emails
have identical transport (Gmail SMTP with STARTTLS), dry-run behavior,
and error handling as the existing decision/anomaly emails.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.decision.escalation import queue as esc_queue
from app.decision.escalation import templates
from app.persistence.postgres import postgres_store

log = logging.getLogger(__name__)


async def fire_due_attempts() -> int:
    """
    One cycle: find due escalations, send emails, update state.
    Returns the number of attempts fired.
    """
    try:
        due = await esc_queue.list_due()
    except Exception:
        log.exception("escalation_worker: list_due failed")
        return 0

    if not due:
        return 0

    fired = 0
    for esc in due:
        try:
            await _fire_one(esc)
            fired += 1
        except Exception:
            log.exception("escalation_worker: failed to fire %s", esc.id)
    return fired


async def _fire_one(esc) -> None:
    # Load decision + anomaly so templates have full data
    decision_row = await postgres_store.get_decision(esc.decision_id)
    if not decision_row:
        log.warning("escalation_worker: decision %s not found, skipping", esc.decision_id)
        return

    from app.decision.log import row_to_decision
    try:
        decision = row_to_decision(decision_row)
    except Exception:
        log.exception("escalation_worker: row_to_decision failed for %s", esc.decision_id)
        decision = decision_row  # type: ignore[assignment]

    anomaly = await postgres_store.get_anomaly(esc.anomaly_id)

    # Select the template for the *next* attempt
    next_attempt = esc.attempt + 1
    if next_attempt == 1:
        builder = templates.initial
    elif next_attempt == 2:
        builder = templates.reminder
    else:
        builder = templates.final_failure

    subject, text, html = builder(esc, decision, anomaly)

    # Send via the existing emailer transport
    recipient = (
        getattr(settings, "NOTIFY_RECIPIENT", "")
        or settings.SMTP_FROM
        or settings.SMTP_USER
    )
    sent = False
    error: str | None = None
    try:
        from app.notifications.emailer import _send
        sent, error = await _send(recipient, subject, text, html)
    except Exception as e:
        log.exception("escalation_worker: _send failed for %s", esc.id)
        error = str(e)

    await esc_queue.record_attempt(
        esc,
        subject=subject,
        body=text,
        sent=sent,
        error=error,
    )

    # Also persist to the `notifications` table for unified audit
    try:
        await postgres_store.save_notification({
            "id": f"NTF-{esc.id}-{next_attempt}",
            "kind": "ESCALATION",
            "anomaly_id": esc.anomaly_id,
            "decision_id": esc.decision_id,
            "service_id": esc.service_id,
            "recipient": recipient,
            "sender": settings.SMTP_FROM or settings.SMTP_USER,
            "subject": subject,
            "body": text,
            "status": "SENT" if sent else ("FAILED" if error else "SKIPPED"),
            "error": error,
        })
    except Exception:
        log.exception("escalation_worker: save_notification failed")

    log.info(
        "Escalation %s: attempt %d/%d %s (status now %s)",
        esc.id, esc.attempt, esc.max_attempts,
        "sent" if sent else f"failed ({error})",
        esc.status.value,
    )


def start_escalation_worker(scheduler: AsyncIOScheduler) -> None:
    """Register the escalation worker on the scheduler."""
    interval = getattr(settings, "ESCALATION_POLL_INTERVAL_SEC", 30)
    scheduler.add_job(
        fire_due_attempts,
        "interval",
        seconds=interval,
        id="escalation_worker",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("Escalation worker scheduled (every %ss)", interval)