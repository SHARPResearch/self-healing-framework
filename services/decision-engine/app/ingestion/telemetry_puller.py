# services\decision-engine\app\ingestion\telemetry_puller.py
"""
Pull raw telemetry from Component 1 (ml-backend) into the local ring buffer.

Component 1 owns detection and already scrapes Prometheus (live mode) or replays
SMD windows (replay mode). Its `/api/services/{id}/metrics` endpoint returns the
same feature rows it scored, which is what Component 2 slices before and after
an anomaly. Pulling from this endpoint keeps both sides on one fleet and one
clock; the old C2-only mock endpoint produced empty slices for live services.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.ingestion.ring_buffer import _as_utc, ring_buffer

log = logging.getLogger(__name__)


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _catalog_entry(service_id: str) -> dict[str, Any]:
    try:
        from app.integration.catalog import resolve_catalog

        return resolve_catalog().get(service_id, {})
    except Exception:
        return {}


def _infra_payload(service_id: str, row: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    features = row.get("features") or {}
    cpu_rate = _number(features.get("cpu_rate"))
    memory_used = _number(features.get("memory_used"))
    network_rx = _number(features.get("network_rx"))
    network_tx = _number(features.get("network_tx"))
    disk_read = _number(features.get("disk_io_read"))
    disk_write = _number(features.get("disk_io_write"))
    cpu_throttled = _number(features.get("cpu_throttled"))
    restarts = _number(features.get("restarts"))
    ready_ratio = _number(features.get("ready_ratio"))

    pod_count = int(entry.get("replicas") or 1)
    ready_pods = round(ready_ratio * pod_count) if ready_ratio is not None else pod_count
    mem_limit_mb = _number(entry.get("mem_limit_mb")) or 4096.0
    mem_used_mb = memory_used / 1048576 if memory_used is not None else None
    mem_pct = min(1.0, mem_used_mb / mem_limit_mb) if mem_used_mb is not None else None
    timestamp = _as_utc(row.get("time") or datetime.now(timezone.utc)).isoformat()

    return {
        "service_id": service_id,
        "service_name": entry.get("display_name") or entry.get("service_name") or service_id,
        "layer": entry.get("layer"),
        "team": entry.get("team"),
        "runtime": entry.get("runtime", "k8s"),
        "version": entry.get("version", "unknown"),
        "region": entry.get("region", "local"),
        "node_pool": entry.get("node_pool", "default"),
        "node": None,
        "container_image": None,
        "uptime_seconds": None,
        "pod_count": pod_count,
        "ready_pods": ready_pods,
        "ready_ratio": ready_ratio,
        "restarts_last_5m": int(restarts) if restarts is not None else None,
        "cpu": {
            "usage_pct": cpu_rate,
            "cores_used": cpu_rate,
            "limit_cores": 1.0,
            "throttled_pct": cpu_throttled,
        },
        "memory": {
            "used_mb": mem_used_mb,
            "limit_mb": mem_limit_mb,
            "pct": mem_pct,
            "rss_mb": None,
            "heap_mb": None,
            "oom_kills": None,
        },
        "network": {
            "rx_kbps": network_rx * 8 / 1000 if network_rx is not None else None,
            "tx_kbps": network_tx * 8 / 1000 if network_tx is not None else None,
            "rx_errors": None,
            "tx_dropped": None,
        },
        "disk": {
            "read_iops": disk_read,
            "write_iops": disk_write,
            "used_pct": None,
        },
        "gc": None,
        "timestamp": timestamp,
    }


def _app_payload(service_id: str, row: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    features = row.get("features") or {}
    cpu_rate = _number(features.get("cpu_rate"))
    network_rx = _number(features.get("network_rx"))
    network_tx = _number(features.get("network_tx"))
    throughput = network_rx + network_tx if network_rx is not None and network_tx is not None else None
    timestamp = _as_utc(row.get("time") or datetime.now(timezone.utc)).isoformat()

    return {
        "service_id": service_id,
        "service_name": entry.get("display_name") or entry.get("service_name") or service_id,
        "layer": entry.get("layer"),
        "team": entry.get("team"),
        "timestamp": timestamp,
        "requests_per_sec": None,
        "throughput_bytes_per_sec": throughput,
        "latency_ms": {},
        "error_rate": None,
        "error_budget_remaining_pct": None,
        "status_codes": {},
        "active_connections": None,
        "queue_depth": None,
        "queue_lag_ms": None,
        "db_query_p95_ms": None,
        "db_connection_pool_used": None,
        "db_connection_pool_max": None,
        "cache_hit_rate": None,
        "cache_evictions_per_min": None,
        "upstream_calls": [],
        "endpoints": [],
        "saturation_pct": cpu_rate,
    }


async def pull_once() -> None:
    from app.integration.component1 import fetch_services

    states = await fetch_services()
    service_ids = [str(s.get("serviceId")) for s in states if s.get("serviceId")]
    if not service_ids:
        log.debug("Component 1 reported no services; telemetry pull skipped")
        return

    base = (getattr(settings, "COMPONENT1_URL", "") or "http://localhost:8002").rstrip("/")
    async with httpx.AsyncClient(timeout=5.0) as client:
        for sid in service_ids:
            entry = _catalog_entry(sid)
            try:
                response = await client.get(
                    f"{base}/api/services/{sid}/metrics",
                    params={"limit": 200},
                )
                if response.status_code != 200:
                    log.warning("C1 metrics for %s returned HTTP %s", sid, response.status_code)
                    continue
                rows = response.json()
                if not isinstance(rows, list) or not rows:
                    log.debug("No C1 metric rows for %s yet", sid)
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    timestamp = _as_utc(row.get("time") or datetime.now(timezone.utc))
                    key = str(row.get("service_id") or sid)
                    ring_buffer.push_infra(key, timestamp, _infra_payload(sid, row, entry))
                    ring_buffer.push_app(key, timestamp, _app_payload(sid, row, entry))
                log.debug("Pulled %d C1 metric rows for %s", len(rows), sid)
            except Exception as exc:
                log.warning("C1 telemetry pull failed for %s: %s", sid, exc)


def start_telemetry_puller(scheduler: AsyncIOScheduler):
    scheduler.add_job(
        pull_once,
        "interval",
        seconds=settings.TELEMETRY_POLL_INTERVAL_SEC,
        id="telemetry_puller",
        replace_existing=True,
        max_instances=1,
    )
    log.info("Telemetry puller scheduled (poll every %ss)", settings.TELEMETRY_POLL_INTERVAL_SEC)
