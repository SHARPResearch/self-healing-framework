# services\decision-engine\app\ingestion\anomaly_sink.py
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
from app.integration.component1 import (
    anomaly_from_state,
    by_service,
    fetch_services,
    is_unhealthy,
)

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
        # Component 1 owns detection. Poll its per-service state once per cycle;
        # if it is down, fall back to the local health table so the pipeline keeps
        # running (and logs that it is running on degraded input).
        component1 = by_service(await fetch_services())
        use_component1 = bool(component1)
        if not use_component1:
            log.warning(
                "Component 1 unavailable — anomaly polling falls back to local mock health"
            )

        # Component 1's fleet is the source of truth in live mode; the local
        # catalog is still polled so replay/demo scenarios keep working.
        for sid in sorted(set(SERVICES) | set(component1)):
            c1 = component1.get(sid)
            if use_component1:
                if c1 is None:
                    # Component 1 does not track this service; nothing to detect.
                    continue
                current_health = str(c1.get("status") or "healthy")
                unhealthy = is_unhealthy(c1)
            else:
                current_health = _health(sid)  # local fallback
                unhealthy = current_health != "healthy"

            state = await postgres_store.get_incident_state(sid)
            incident_open = bool(state and state.get("incident_start"))

            # ── HEALTHY ─────────────────────────────────────────
            if not unhealthy:
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

                # Anomaly signal: Component 1 when available, local mock otherwise.
                if use_component1 and c1 is not None:
                    a = anomaly_from_state(
                        c1, make_incident_id(sid, detected_at), detected_at
                    )
                else:
                    a = _anomaly(sid)
                if a is None:
                    # Service says unhealthy but no anomaly signal was built —
                    # should not happen, but be defensive
                    log.warning(
                        "Health=%s but no anomaly signal for %s",
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

                # Notify the operator that a new anomaly/incident opened.
                try:
                    from app.notifications.emailer import notify_anomaly_detected
                    await notify_anomaly_detected({
                        **a,
                        "id": incident_id,
                        "detected_at": detected_at.isoformat(),
                    })
                except Exception:
                    log.exception("notify_anomaly_detected failed for %s", incident_id)

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
# async def _capture_phase1(anomaly_id: str, service_id: str, detected_at: datetime):
#     w_from = detected_at - timedelta(seconds=settings.SNAPSHOT_BEFORE_SEC)
#     w_to = detected_at

#     try:
#         infra_pts = ring_buffer.slice_infra(service_id, w_from, w_to)
#         app_pts = ring_buffer.slice_app(service_id, w_from, w_to)

#         for p in infra_pts:
#             await timescale_store.insert_infra_snapshot(
#                 anomaly_id=anomaly_id,
#                 time_=p["time"],
#                 service_id=service_id,
#                 payload=p["data"],
#             )
#         for p in app_pts:
#             await timescale_store.insert_app_snapshot(
#                 anomaly_id=anomaly_id,
#                 time_=p["time"],
#                 service_id=service_id,
#                 payload=p["data"],
#             )

#         log.info(
#             "Phase 1 for %s: %d infra + %d app points (%s .. %s)",
#             anomaly_id, len(infra_pts), len(app_pts), w_from, w_to,
#         )
#     except Exception:
#         log.exception("Phase 1 failed for %s", anomaly_id)
# ─────────────────────────────────────────────────────────────────────
# Phase 1 — BEFORE window (immediate)
# ─────────────────────────────────────────────────────────────────────
async def _capture_phase1(anomaly_id: str, service_id: str, detected_at: datetime):
    """
    Capture the BEFORE window [T - SNAPSHOT_BEFORE_SEC, T] into Timescale.

    Defensive guarantees:
      * All datetimes coerced to timezone-aware UTC before any comparison.
      * If the ring buffer has no entries for `service_id` under the exact key,
        try common normalizations (- / _ / space). If still nothing, try a
        prefix match. If still nothing, log the full key set at ERROR — that
        is the "you're slicing the wrong fleet" signal and must never be
        silent again.
      * If the window start predates the oldest buffered point, clamp forward
        to the oldest point and log a WARNING. A fresh boot otherwise silently
        captures 0 rows.
      * If the window end is before the oldest buffered point, abort with a
        WARNING — the window is entirely in the past.
      * Per-point insert failures are logged individually; one bad row does
        not abort the capture.
      * The final log line reports buffer size, per-side sliced counts, and
        per-side written counts, so "0 points" is diagnosable from one line.
    """
    detected_at = _as_utc(detected_at)
    w_from = detected_at - timedelta(seconds=settings.SNAPSHOT_BEFORE_SEC)
    w_to = detected_at

    # ── Resolve the service key against what the buffer actually holds ──
    resolved = _resolve_buffer_key(service_id)
    if resolved is None:
        log.error(
            "Phase 1 for %s: service_id %r not in ring buffer and no "
            "normalization matched. buffer_keys=%s",
            anomaly_id, service_id, sorted(ring_buffer.infra.keys()),
        )
        return

    if resolved != service_id:
        log.warning(
            "Phase 1 for %s: service_id %r resolved to buffer key %r",
            anomaly_id, service_id, resolved,
        )
        service_id = resolved

    # ── Inspect the buffer BEFORE slicing so we can clamp and log ──────
    infra_buf = ring_buffer.infra.get(service_id) or []
    app_buf = ring_buffer.app.get(service_id) or []

    if not infra_buf and not app_buf:
        log.error(
            "Phase 1 for %s: ring buffer key %r exists but is EMPTY — "
            "nothing to capture (window %s .. %s)",
            anomaly_id, service_id, w_from.isoformat(), w_to.isoformat(),
        )
        return

    # Oldest buffered point across both deques
    oldest_candidates = []
    if infra_buf:
        oldest_candidates.append(_as_utc(infra_buf[0]["time"]))
    if app_buf:
        oldest_candidates.append(_as_utc(app_buf[0]["time"]))
    oldest = min(oldest_candidates)

    if w_to < oldest:
        log.warning(
            "Phase 1 for %s: window END %s is BEFORE buffer oldest %s — "
            "nothing to capture",
            anomaly_id, w_to.isoformat(), oldest.isoformat(),
        )
        return

    if w_from < oldest:
        log.warning(
            "Phase 1 for %s: window START %s predates buffer oldest %s — "
            "clamping to oldest. buffer=%d infra / %d app points",
            anomaly_id, w_from.isoformat(), oldest.isoformat(),
            len(infra_buf), len(app_buf),
        )
        w_from = oldest

    # ── Slice and write ────────────────────────────────────────────────
    try:
        infra_pts = ring_buffer.slice_infra(service_id, w_from, w_to)
        app_pts = ring_buffer.slice_app(service_id, w_from, w_to)

        infra_written = 0
        for p in infra_pts:
            try:
                await timescale_store.insert_infra_snapshot(
                    anomaly_id=anomaly_id,
                    time_=_as_utc(p["time"]),
                    service_id=service_id,
                    payload=p["data"],
                )
                infra_written += 1
            except Exception:
                log.exception(
                    "Phase 1 for %s: failed to insert infra point at %s",
                    anomaly_id, p["time"],
                )

        app_written = 0
        for p in app_pts:
            try:
                await timescale_store.insert_app_snapshot(
                    anomaly_id=anomaly_id,
                    time_=_as_utc(p["time"]),
                    service_id=service_id,
                    payload=p["data"],
                )
                app_written += 1
            except Exception:
                log.exception(
                    "Phase 1 for %s: failed to insert app point at %s",
                    anomaly_id, p["time"],
                )

        log.info(
            "Phase 1 for %s: sliced %d infra + %d app, wrote %d infra + %d app "
            "(buffer=%d/%d, window %s .. %s)",
            anomaly_id,
            len(infra_pts), len(app_pts),
            infra_written, app_written,
            len(infra_buf), len(app_buf),
            w_from.isoformat(), w_to.isoformat(),
        )

        if infra_written == 0 and app_written == 0:
            log.error(
                "Phase 1 for %s: sliced 0 rows despite non-empty buffer — "
                "window=[%s .. %s], buffer_oldest=%s buffer_newest_infra=%s "
                "buffer_newest_app=%s",
                anomaly_id,
                w_from.isoformat(), w_to.isoformat(),
                oldest.isoformat(),
                _as_utc(infra_buf[-1]["time"]).isoformat() if infra_buf else "empty",
                _as_utc(app_buf[-1]["time"]).isoformat() if app_buf else "empty",
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