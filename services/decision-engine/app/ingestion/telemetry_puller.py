# # services\decision-engine\app\ingestion\telemetry_puller.py
# """
# Background job: every N seconds, pull telemetry from the mock generator
# directly (no HTTP round-trip) and push into the ring buffer.
# """
# import logging
# from datetime import datetime, timezone
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from app.config import settings
# from app.ingestion.ring_buffer import ring_buffer
# from app.api.routes.mock_data import _infra, _app, SERVICES

# log = logging.getLogger(__name__)


# # async def pull_once():
# #     try:
# #         # now = datetime.now(timezone.utc)
# #         for sid in SERVICES:
# #             now = datetime.now(timezone.utc)   
# #             infra = _infra(sid)
# #             app_data = _app(sid)
# #             ring_buffer.push_infra(sid, now, infra)
# #             ring_buffer.push_app(sid, now, app_data)

# #         stats = ring_buffer.stats()
# #         log.info(
# #             "Telemetry pulled: %s infra pts, %s app pts",
# #             stats["total_infra_points"], stats["total_app_points"],
# #         )
# #     except Exception:
# #         log.exception("Telemetry pull failed")

# async def pull_once():
#     try:
#         # ── LIVE: pull per-service telemetry from Component 1 ──
#         # Component 1 owns the fleet it sees (the k8s cluster), so its service
#         # list IS the key set the anomaly poller will look up. Pulling from the
#         # mock fleet instead means every C1 anomaly finds no buffer slice.
#         from app.integration.component1 import fetch_services, by_service
#         from app.integration.component1 import is_unhealthy  # not used, but harmless
#         # The actual per-service telemetry: prefer component1's telemetry API.
#         from app.integration import telemetry as c1_telemetry  # see Edit 2

#         services = await fetch_services()
#         c1_map = by_service(services)

#         if not c1_map:
#             log.warning("Component 1 unreachable — telemetry pull skipped (no fallback)")
#             return

#         for sid, record in c1_map.items():
#             now = datetime.now(timezone.utc)
#             infra = c1_telemetry.build_infra(record)
#             app_data = c1_telemetry.build_app(record)
#             ring_buffer.push_infra(sid, now, infra)
#             ring_buffer.push_app(sid, now, app_data)

#         stats = ring_buffer.stats()
#         log.info(
#             "Telemetry pulled from C1 (%d services): %s infra pts, %s app pts",
#             len(c1_map), stats["total_infra_points"], stats["total_app_points"],
#         )
#     except Exception:
#         log.exception("Telemetry pull failed")


# def start_telemetry_puller(scheduler: AsyncIOScheduler):
#     scheduler.add_job(
#         pull_once,
#         "interval",
#         seconds=settings.TELEMETRY_POLL_INTERVAL_SEC,
#         id="telemetry_puller",
#         replace_existing=True,
#         max_instances=1,
#     )
#     log.info("Telemetry puller scheduled every %ss", settings.TELEMETRY_POLL_INTERVAL_SEC)


# services/decision-engine/app/ingestion/telemetry_puller.py
"""
Background job: every N seconds, pull telemetry for the services Component 1
actually sees, and push it into the ring buffer under Component 1's service id.

Why this matters: `anomaly_sink.poll_anomalies` reads detection state from
Component 1 and then slices the ring buffer by `service_id`. If the puller
writes under the mock catalog's ids (`redis-cache`, `payment-service`, ...)
while C1 emits `redis-cart`, `paymentservice`, ... , every slice returns 0
points and `_capture_phase1` silently stores nothing. That mismatch was the
bug that starved the snapshot tables; this file keeps the two sides aligned by
using C1's ids as the ring-buffer keys.
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.ingestion.ring_buffer import ring_buffer
from app.integration.component1 import fetch_services, by_service
from app.api.routes.mock_data import _infra, _app  # fallback only

log = logging.getLogger(__name__)


def _build_infra_payload(record: dict) -> dict:
    # """
    # Turn a Component 1 /api/services record into an infra snapshot payload
    # that timescale_store.insert_infra_snapshot accepts.

    # C1's record shape (from /api/services):
    #   {"serviceId", "displayName", "status", "anomalyScore", "scoreHistory",
    #    "modelVersion", "phase", "driftDetected", "quarantine", "openQueries",
    #    "smdEntity", "source", ...}

    # We map anomalyScore -> cpu proxy and status -> ready_pods so downstream
    # rules that read `cpu`/`mem`/`ready_pods` have something real. If C1 later
    # exposes explicit infra metrics, extend this mapping — the point is that
    # the ring buffer now carries C1's data under C1's service ids.
    # """
    score = float(record.get("anomalyScore") or 0.0)
    status = (record.get("status") or "").lower()
    healthy = status in ("healthy", "watch", "stable")
    return {
        "service_id": record.get("serviceId"),
        "service_name": record.get("displayName"),
        "cpu_usage_pct": round(score * 100.0, 4),
        "mem_pct": round(score * 100.0, 4),
        "ready_pods": 1 if healthy else 0,
        "pod_count": 1,
        "phase": record.get("phase"),
        "drift_detected": record.get("driftDetected", False),
        "model_version": record.get("modelVersion"),
        "source": "component1",
    }


def _build_app_payload(record: dict) -> dict:
    score = float(record.get("anomalyScore") or 0.0)
    return {
        "service_id": record.get("serviceId"),
        "service_name": record.get("displayName"),
        "anomaly_score": round(score, 6),
        "status": record.get("status"),
        "open_queries": record.get("openQueries", 0),
        "model_version": record.get("modelVersion"),
        "phase": record.get("phase"),
        "source": "component1",
    }


async def pull_once():
    try:
        services = await fetch_services()
        c1_map = by_service(services)

        if c1_map:
            # LIVE path — C1 is reachable. Push one sample per C1 service,
            # under C1's id. This is the fix: buffer keys now equal the ids
            # that anomaly_sink will slice on.
            for sid, record in c1_map.items():
                now = datetime.now(timezone.utc)
                ring_buffer.push_infra(sid, now, _build_infra_payload(record))
                ring_buffer.push_app(sid, now, _build_app_payload(record))

            stats = ring_buffer.stats()
            log.info(
                "Telemetry pulled from C1 (%d services): %s infra pts, %s app pts",
                len(c1_map), stats["total_infra_points"], stats["total_app_points"],
            )
            return

        # DEGRADED path — C1 unreachable. Fall back to the local mock catalog
        # so the pipeline keeps running in demo mode. Log it loudly; a silent
        # fallback is what hid the id-mismatch bug in the first place.
        log.warning("Component 1 unreachable — pulling from mock catalog (degraded mode)")
        from app.api.routes.mock_data import SERVICES
        now = datetime.now(timezone.utc)
        for sid in SERVICES:
            ring_buffer.push_infra(sid, now, _infra(sid))
            ring_buffer.push_app(sid, now, _app(sid))

        stats = ring_buffer.stats()
        log.info(
            "Telemetry pulled from mock (%d services): %s infra pts, %s app pts",
            len(SERVICES), stats["total_infra_points"], stats["total_app_points"],
        )
    except Exception:
        log.exception("Telemetry pull failed")


def start_telemetry_puller(scheduler: AsyncIOScheduler):
    scheduler.add_job(
        pull_once,
        "interval",
        seconds=settings.TELEMETRY_POLL_INTERVAL_SEC,
        id="telemetry_puller",
        replace_existing=True,
        max_instances=1,
    )
    log.info("Telemetry puller scheduled every %ss", settings.TELEMETRY_POLL_INTERVAL_SEC)