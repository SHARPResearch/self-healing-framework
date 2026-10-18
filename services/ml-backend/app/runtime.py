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
from app.logs import AlarmLog, LogHub, make_line, public as public_log
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
        self.hub = LogHub(http_access=settings.log_http_access)
        self.hub.install()                          # catch uvicorn's own startup lines too
        self._alarms: dict[str, AlarmLog] = {}

    # -- lifecycle ---------------------------------------------------------------------------------
    async def start(self, backing_services: bool = True, replay: bool = True) -> None:
        self.hub.start()
        if backing_services:
            self.store = await make_store(settings.database_url)
            await self.bus.start(settings.redis_url)
        await asyncio.to_thread(self.fleet.build)
        for rt in self.fleet.services.values():
            self.log(rt.service_id, f"warm-up complete on {rt.entity}: {self.fleet.warm_up_rows} rows, "
                     f"model v{rt.manager.registry.production_version} serving, "
                     f"{settings.threshold_method.upper()} threshold {rt.manager.threshold:.4f}",
                     attrs={"entity": rt.entity})
        await self.drain_all()                      # warm-up versions and transitions
        if backing_services and settings.follow_container_logs:
            self.hub.follow_containers(settings.log_containers, await self.store.latest_log_times())
        if replay:
            self._task = asyncio.create_task(self._loop(), name="replay")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.hub.stop()
        await self.flush_logs()
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
            await self.flush_logs()
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
            episode = self._alarms.setdefault(rt.service_id, AlarmLog()).update(
                res.step, bool(res.alarm), display)
            if episode:
                kind, attrs = episode
                if kind == "raised":
                    self.log(rt.service_id, f"alarm raised at step {attrs['step']} "
                             f"(score {attrs['score']}, model v{res.version})", "warn", attrs)
                else:
                    self.log(rt.service_id, f"alarm cleared: steps {attrs['from_step']} to {attrs['to_step']}, "
                             f"peak score {attrs['peak']}, {attrs['alarming_events']} alarming events",
                             "info", attrs)
            await self.drain(rt)

    # -- logs --------------------------------------------------------------------------------------
    def log(self, service_id: str, message: str, level: str = "info", attrs: Optional[dict] = None) -> None:
        """One line on the Logs page for a monitored service."""
        self.hub.add(make_line(service_id, message, level, source="lifecycle",
                               service_id=service_id, attrs=attrs))

    async def flush_logs(self) -> None:
        """Move buffered log lines (any thread, any source) into the store and out to live tails."""
        lines = self.hub.take()
        if not lines:
            return
        await self.store.write_logs(lines)
        for line in lines:
            await self.bus.publish(envelope("log", line.get("service_id"), public_log(line)))

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
                self.log(rt.service_id, f"model {payload['transition']} "
                         f"v{payload['from_version']} to v{payload['to_version']}: {payload['reason']}"
                         if payload["from_version"] != payload["to_version"] else
                         f"model {payload['transition']} v{payload['to_version']}: {payload['reason']}",
                         "warn" if payload["transition"] == "rollback" else "info",
                         {"transition": payload["transition"], "to_version": payload["to_version"]})
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
                self._log_lifecycle(rt, event, data)
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

    def _log_lifecycle(self, rt: ServiceRuntime, event: str, d: dict) -> None:
        sid = rt.service_id
        if event == "quarantine_opened":
            self.log(sid, f"quarantine opened (trigger: {d.get('trigger')}), observing {d.get('length')} "
                     "events while the serving model keeps scoring", "info", {"trigger": d.get("trigger")})
        elif event == "change_observed":
            self.log(sid, f"change event {d.get('change_event_id')} reached the lifecycle", "info")
        elif event == "lifecycle_decision":
            action = d.get("action")
            self.log(sid, f"decision: {d.get('verdict')} -> {action}: {d.get('reason')}",
                     "warn" if action in ("hold", "ask") else "info",
                     {"verdict": d.get("verdict"), "action": action, "trigger": d.get("trigger")})
        elif event == "operator_query":
            self.log(sid, f"asking the operator ({d.get('query_id')}): new normal or incident?", "warn",
                     {"query_id": d.get("query_id")})
        elif event == "query_answered":
            self.log(sid, f"operator {d.get('operator')} answered {d.get('query_id')}: {d.get('answer')}",
                     "info", {"query_id": d.get("query_id"), "answer": d.get("answer")})
        elif event == "query_expired":
            self.log(sid, f"query {d.get('query_id')} expired unanswered, keeping the serving model",
                     "warn", {"query_id": d.get("query_id")})

    # -- controls ----------------------------------------------------------------------------------
    async def inject(self, service_id: str, kind: str) -> dict:
        info = self.fleet.inject(service_id, kind)
        self.log(service_id, f"demo injection: {kind.replace('_', ' ')} on "
                 f"{len(info.get('features', []))} metrics", "info", {"kind": kind})
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
