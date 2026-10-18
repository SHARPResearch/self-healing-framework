"""
Background job: every N seconds, pull telemetry from the mock generator
directly (no HTTP round-trip) and push into the ring buffer.
"""
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.ingestion.ring_buffer import ring_buffer
from app.api.routes.mock_data import _infra, _app, SERVICES

log = logging.getLogger(__name__)


async def pull_once():
    try:
        now = datetime.now(timezone.utc)
        for sid in SERVICES:
            infra = _infra(sid)
            app_data = _app(sid)
            ring_buffer.push_infra(sid, now, infra)
            ring_buffer.push_app(sid, now, app_data)

        stats = ring_buffer.stats()
        log.info(
            "Telemetry pulled: %s infra pts, %s app pts",
            stats["total_infra_points"], stats["total_app_points"],
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