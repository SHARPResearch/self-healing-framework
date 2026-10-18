"""
runtime.py — wires the fleet, the store and the bus together and runs the replay loop.

The loop advances every service by one telemetry event per tick (REPLAY_EVENTS_PER_SEC ticks per
second), which is exactly what POST /ingest/metrics would do with live Prometheus scrapes (Doc3
Phase 3). Scoring and lifecycle decisions run in ml-pipeline; asynchronous quarantine decisions are
evaluated on background threads and swapped in by DynamicModelManager.process.

Message types published on the bus (and the WebSocket):
  anomaly_score        normalized score, alarm, severity, model version, phase  (throttled)
  quarantine_opened    a drift, change or scheduled trigger opened an observation window
  change_observed      a deployment/config change event reached the lifecycle
  lifecycle_decision   verdict, action, reason and evidence of a closed quarantine
  operator_query       CADAL asks "new normal or incident?" (operator in the loop)
  query_answered / query_expired
  model_transition     a registry transition (register, promote, rollback, checkpoint)
  demo_injection       the presenter injected a deployment / silent change / incident
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from app.bus import Bus, envelope
from app.config import settings
from app.fleet import ServiceFleet, ServiceRuntime
from app.store import MemoryStore, make_store

logger = logging.getLogger(__name__)

TICK_S = 0.05

LIFECYCLE_TYPES = {"quarantine_opened", "change_observed", "lifecycle_decision", "operator_query",
                   "query_answered", "query_expired"}


class Runtime:
    def __init__(self, fleet: Optional[ServiceFleet] = None):
        self.fleet = fleet or ServiceFleet()
        self.store: MemoryStore = MemoryStore()
        self.bus = Bus()
        self.events_per_sec = settings.replay_events_per_sec
        self.paused = False
        self.tick = 0
        self.started_at = time.time()
        self._task: Optional[asyncio.Task] = None
        self._pending_rows: list[dict] = []
        self._last_flush = time.monotonic()

    # -- lifecycle ---------------------------------------------------------------------------------
    async def start(self, backing_services: bool = True, replay: bool = True) -> None:
        if backing_services:
            self.store = await make_store(settings.database_url)
            await self.bus.start(settings.redis_url)
        await asyncio.to_thread(self.fleet.build)
        await self.drain_all()                      # warm-up versions and transitions
        if replay:
            self._task = asyncio.create_task(self._loop(), name="replay")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.flush_rows()
        await self.store.stop()
        await self.bus.stop()

    # -- the loop ----------------------------------------------------------------------------------
    async def _loop(self) -> None:
        # Wake every TICK_S and run as many steps as the elapsed time has earned. Sleeping once per
        # event instead caps the rate on Windows, where timer resolution is ~15 ms.
        credit, last = 0.0, time.monotonic()
        while True:
            now = time.monotonic()
            if self.paused:
                credit = 0.0
            else:
                credit = min(credit + (now - last) * self.events_per_sec, self.events_per_sec * 0.5)
                while credit >= 1.0:
                    await self.step_all()
                    credit -= 1.0
            last = now
            if time.monotonic() - self._last_flush >= 1.0:
                await self.flush_rows()
            await asyncio.sleep(TICK_S)

    async def step_all(self) -> None:
        self.tick += 1
        now = datetime.now(timezone.utc)
        for rt in self.fleet.services.values():
            x, res, display = self.fleet.process(rt)
            self._pending_rows.append({
                "time": now, "service_id": rt.service_id, "anomaly_score": display,
                "severity": self.fleet.severity(rt), "drift_detected": res.phase != "stable",
                "features": self.fleet.snapshot_features(x), "alarm": bool(res.alarm),
                "threshold": 0.5, "model_version": res.version, "phase": res.phase,
            })
            if res.step % settings.score_push_every == 0:
                await self.bus.publish(envelope("anomaly_score", rt.service_id, {
                    "step": res.step, "score": round(display, 4), "alarm": bool(res.alarm),
                    "severity": self.fleet.severity(rt), "version": res.version,
                    "phase": res.phase, "threshold": 0.5,
                    "trigger": getattr(rt.manager, "_q_trigger", None) if res.phase != "stable" else None,
                }))
            await self.drain(rt)

    async def flush_rows(self) -> None:
        rows, self._pending_rows = self._pending_rows, []
        self._last_flush = time.monotonic()
        if rows:
            await self.store.write_metric_events(rows)

    # -- outbox -> store + bus ---------------------------------------------------------------------
    async def drain_all(self) -> None:
        for rt in self.fleet.services.values():
            await self.drain(rt)

    async def drain(self, rt: ServiceRuntime) -> None:
        while rt.outbox.events:
            kind, payload = rt.outbox.events.popleft()
            if kind == "transition":
                await self.store.write_transition(payload)
                await self.bus.publish(envelope("model_transition", rt.service_id, payload))
                if payload["transition"] in ("promote", "rollback"):
                    rt.last_action = f"Model {payload['transition']} to v{payload['to_version']}"
                    rt.last_action_at = datetime.now(timezone.utc).isoformat()
            elif kind == "version":
                await self.store.write_version(payload)
            elif kind == "lifecycle":
                event = payload.get("event")
                data = {k: v for k, v in payload.items() if k != "event"}
                if event == "lifecycle_decision":
                    await self.store.write_decision(data)
                    rt.drift_flag = data.get("action") in ("promote", "ask", "hold")
                elif event in ("operator_query", "query_answered", "query_expired"):
                    await self.store.write_query({**data, "service_id": rt.service_id})
                elif event == "change_observed":
                    await self.store.write_change({"service_id": rt.service_id, "kind": "deployment",
                                                   "detail": data})
                if event in LIFECYCLE_TYPES:
                    await self.bus.publish(envelope(event, rt.service_id, data))

    # -- controls ----------------------------------------------------------------------------------
    async def inject(self, service_id: str, kind: str) -> dict:
        info = self.fleet.inject(service_id, kind)
        await self.bus.publish(envelope("demo_injection", service_id, info))
        return info

    async def reset(self) -> None:
        self.paused = True
        self.fleet = ServiceFleet(self.fleet.specs, self.fleet.warm_up_rows)
        await asyncio.to_thread(self.fleet.build)
        await self.drain_all()
        self.paused = False
        await self.bus.publish(envelope("demo_reset", None, {}))


runtime = Runtime()
