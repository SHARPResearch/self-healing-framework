"""
Anomaly ingestion.

When a new anomaly is detected at time T:
  PHASE 1 (immediate)  → slice [T-3min, T] from ring buffer → insert
  PHASE 2 (at T+3min)  → slice [T, T+3min] from ring buffer → insert
  Then mark anomaly as 'captured'.

This is necessary because the ring buffer only holds recent history;
we must grab the pre-window while it's still fresh.
"""
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.ingestion.ring_buffer import ring_buffer
from app.persistence.postgres import postgres_store
from app.persistence.timescale import timescale_store
from app.api.routes.mock_data import _anomaly, SERVICES, _health

log = logging.getLogger(__name__)


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ─────────────────────────────────────────────────────────────────
# Polling for new anomalies
# ─────────────────────────────────────────────────────────────────
# async def poll_anomalies(scheduler: AsyncIOScheduler):
#     try:
#         for sid in SERVICES:
#             a = _anomaly(sid)
#             if a is None:
#                 continue

#             detected_at = _parse_ts(a["detected_at"])
#             inserted = await postgres_store.save_anomaly({
#                 **a,
#                 "detected_at": detected_at,
#             })

#             if not inserted:
#                 continue

#             log.info("New anomaly saved: %s on %s", a["id"], sid)

#             # PHASE 1 — capture the BEFORE window right now
#             await _capture_phase1(a["id"], sid, detected_at)

#             # PHASE 2 — schedule the AFTER window for T + AFTER_SEC
#             run_at = detected_at + timedelta(seconds=settings.SNAPSHOT_AFTER_SEC)
#             scheduler.add_job(
#                 _capture_phase2,
#                 "date",
#                 run_date=run_at,
#                 args=[a["id"], sid, detected_at],
#                 id=f"snap2-{a['id']}",
#                 replace_existing=True,
#                 misfire_grace_time=300,
#             )
#             log.info("Scheduled phase 2 for %s at %s", a["id"], run_at.isoformat())
#     except Exception:
#         log.exception("Anomaly poll failed")

async def poll_anomalies(scheduler: AsyncIOScheduler):
    """
    Incident-aware anomaly poller.

    For each service:
      - If healthy → close any open incident (mark state healthy)
      - If unhealthy and NO incident open → create a NEW anomaly row,
        start phase 1, schedule phase 2
      - If unhealthy and incident OPEN → do nothing (dedupe by incident,
        NOT by wall clock)

    This is the production behavior: one anomaly per incident, regardless
    of how many polls happen during that incident.
    """
    try:
        for sid in SERVICES:
            current_health = _health(sid)          # live health (mock for now)
            state = await postgres_store.get_incident_state(sid)
            incident_open = bool(state and state.get("incident_start"))

            # ── HEALTHY ─────────────────────────────────────────
            if current_health == "healthy":
                if incident_open:
                    await postgres_store.close_incident(sid)
                    log.info(
                        "Incident CLOSED for %s (was %s since %s)",
                        sid, state["incident_id"], state["incident_start"],
                    )
                continue

            # ── UNHEALTHY, NO INCIDENT → NEW INCIDENT ──────────
            if not incident_open:
                detected_at = datetime.now(timezone.utc)

                # Build anomaly signal from mock (real component 1 later)
                a = _anomaly(sid)
                if a is None:
                    # Service says unhealthy but mock returns no anomaly —
                    # should not happen, but be defensive
                    log.warning(
                        "Health=%s but _anomaly()=None for %s",
                        current_health, sid,
                    )
                    continue

                # Override ID with incident-based ID
                incident_id = make_incident_id(sid, detected_at)
                a["id"] = incident_id
                a["detected_at"] = detected_at.isoformat()

                inserted = await postgres_store.save_anomaly({
                    **a,
                    "detected_at": detected_at,
                })
                if not inserted:
                    # Race condition or prior partial state — skip
                    log.warning("save_anomaly returned False for %s", incident_id)
                    continue

                # Record incident state
                await postgres_store.set_incident_state(
                    sid, current_health, detected_at, incident_id
                )

                log.info(
                    "NEW incident STARTED: %s (service=%s, health=%s)",
                    incident_id, sid, current_health,
                )

                # Phase 1 — capture BEFORE window
                await _capture_phase1(incident_id, sid, detected_at)

                # Schedule phase 2 at T + SNAPSHOT_AFTER_SEC
                run_at = detected_at + timedelta(seconds=settings.SNAPSHOT_AFTER_SEC)
                scheduler.add_job(
                    _capture_phase2,
                    "date",
                    run_date=run_at,
                    args=[incident_id, sid, detected_at],
                    id=f"snap2-{incident_id}",
                    replace_existing=True,
                    misfire_grace_time=300,
                )
                log.info("Scheduled phase 2 for %s at %s", incident_id, run_at.isoformat())
                continue

            # ── UNHEALTHY, INCIDENT OPEN → DO NOTHING ──────────
            # Just update last_seen_at for observability
            await postgres_store.set_incident_state(
                sid,
                current_health,
                state.get("incident_start"),
                state.get("incident_id"),
            )

    except Exception:
        log.exception("Anomaly poll failed")


def make_incident_id(service_id: str, incident_start: datetime) -> str:
    """
    Production-grade anomaly ID.
    Format: ANM-{service_id}-{YYYYMMDDTHHMMSSZ}
    Same incident → same ID (deduplication).
    New incident → new ID.
    """
    ts = incident_start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"ANM-{service_id}-{ts}"

# ─────────────────────────────────────────────────────────────────
# Phase 1 — BEFORE window (immediate)
# ─────────────────────────────────────────────────────────────────
async def _capture_phase1(anomaly_id: str, service_id: str, detected_at: datetime):
    w_from = detected_at - timedelta(seconds=settings.SNAPSHOT_BEFORE_SEC)
    w_to = detected_at

    try:
        infra_pts = ring_buffer.slice_infra(service_id, w_from, w_to)
        app_pts = ring_buffer.slice_app(service_id, w_from, w_to)

        for p in infra_pts:
            await timescale_store.insert_infra_snapshot(
                anomaly_id=anomaly_id,
                time_=p["time"],
                service_id=service_id,
                payload=p["data"],
            )
        for p in app_pts:
            await timescale_store.insert_app_snapshot(
                anomaly_id=anomaly_id,
                time_=p["time"],
                service_id=service_id,
                payload=p["data"],
            )

        log.info(
            "Phase 1 for %s: %d infra + %d app points (%s .. %s)",
            anomaly_id, len(infra_pts), len(app_pts), w_from, w_to,
        )
    except Exception:
        log.exception("Phase 1 failed for %s", anomaly_id)


# ─────────────────────────────────────────────────────────────────
# Phase 2 — AFTER window (T + AFTER_SEC)
# ─────────────────────────────────────────────────────────────────
async def _capture_phase2(anomaly_id: str, service_id: str, detected_at: datetime):
    w_from = detected_at
    w_to = detected_at + timedelta(seconds=settings.SNAPSHOT_AFTER_SEC)

    try:
        infra_pts = ring_buffer.slice_infra(service_id, w_from, w_to)
        app_pts = ring_buffer.slice_app(service_id, w_from, w_to)

        for p in infra_pts:
            await timescale_store.insert_infra_snapshot(
                anomaly_id=anomaly_id,
                time_=p["time"],
                service_id=service_id,
                payload=p["data"],
            )
        for p in app_pts:
            await timescale_store.insert_app_snapshot(
                anomaly_id=anomaly_id,
                time_=p["time"],
                service_id=service_id,
                payload=p["data"],
            )

        await postgres_store.mark_snapshot_captured(anomaly_id, w_from, w_to)
        log.info(
            "Phase 2 for %s: %d infra + %d app points (%s .. %s)",
            anomaly_id, len(infra_pts), len(app_pts), w_from, w_to,
        )
    except Exception:
        log.exception("Phase 2 failed for %s", anomaly_id)
        await postgres_store.mark_snapshot_failed(anomaly_id)


# ─────────────────────────────────────────────────────────────────
# Cleanup — retry old pending anomalies at startup
# ─────────────────────────────────────────────────────────────────
async def resume_pending_snapshots(scheduler: AsyncIOScheduler):
    """On startup, look for any pending anomalies and schedule their phase 2."""
    try:
        due = await postgres_store.pending_snapshots_due()
        for anomaly in due:
            run_at = max(
                anomaly["detected_at"] + timedelta(seconds=settings.SNAPSHOT_AFTER_SEC),
                datetime.now(timezone.utc),
            )
            scheduler.add_job(
                _capture_phase2,
                "date",
                run_date=run_at,
                args=[anomaly["id"], anomaly["service_id"], anomaly["detected_at"]],
                id=f"snap2-{anomaly['id']}",
                replace_existing=True,
                misfire_grace_time=300,
            )
            log.info("Rescheduled phase 2 for %s", anomaly["id"])
    except Exception:
        log.exception("Resume pending failed")


def start_anomaly_sink(scheduler: AsyncIOScheduler):
    scheduler.add_job(
        poll_anomalies,
        "interval",
        seconds=settings.ANOMALY_POLL_INTERVAL_SEC,
        args=[scheduler],
        id="anomaly_poller",
        replace_existing=True,
        max_instances=1,
    )
    log.info("Anomaly sink scheduled (poll every %ss)", settings.ANOMALY_POLL_INTERVAL_SEC)