"""
live.py — the fleet in live mode: Online Boutique on Kubernetes, scored from Prometheus.

LiveFleet is ServiceFleet with a different source of rows. Every Online Boutique Deployment
(except the load generator) becomes a service whose id is its `app` label, the same id the
Kubernetes deployment watcher reports, so real rollouts reach the right lifecycle manager.
Each service warms up on its own recent history from Prometheus and then gets one row per
scrape. Everything after that (scoring, CADAL, registry, outbox) is the replay code unchanged.

Pacing is accelerated: one lifecycle "day" is LIVE_LIFECYCLE_DAY_MINUTES of live data.
"""

import logging
import threading
from dataclasses import replace
from typing import Optional

import app.core.pipeline_path  # noqa: F401
import pandas as pd
from src.change_events import QueueChangeEventSource
from src.lifecycle_manager import DynamicModelManager, LifecycleConfig

from app.config import settings
from app.fleet import MirroredRegistry, Outbox, ServiceFleet, ServiceRuntime, normalized_score
from app.prom import OnlineBoutiqueTelemetry, PrometheusClient

logger = logging.getLogger(__name__)


def live_samples_per_day() -> int:
    return max(60, int(round(settings.live_lifecycle_day_minutes * 60 / settings.live_scrape_seconds)))


def live_lifecycle_config() -> LifecycleConfig:
    base = LifecycleConfig(policy="cadal", threshold_method=settings.threshold_method,
                           operator_queries=True, async_decisions=True)
    # for_sampling scales every length, query TTL included, to the live "day"
    return replace(base.for_sampling(live_samples_per_day()), query_budget=3)


def display_name(app: str) -> str:
    """cartservice -> Cart Service, productcatalogservice -> Product Catalog Service."""
    known = {"productcatalogservice": "Product Catalog Service", "redis-cart": "Redis Cart",
             "frontend": "Frontend"}
    if app in known:
        return known[app]
    base = app[:-len("service")] if app.endswith("service") else app
    return f"{base.replace('-', ' ').title()} Service"


class LiveFleet(ServiceFleet):
    def __init__(self, telemetry: Optional[OnlineBoutiqueTelemetry] = None):
        super().__init__(services=[], warm_up_rows=1)
        self.cfg = live_lifecycle_config()
        self.telemetry = telemetry or OnlineBoutiqueTelemetry(
            PrometheusClient(settings.prometheus_url), settings.k8s_namespace)
        self.lock = threading.Lock()
        self.warm_up_rows = 0

    def fresh(self) -> "LiveFleet":
        return LiveFleet(self.telemetry)

    def build(self) -> None:
        names = self.telemetry.services()
        if not names:
            raise RuntimeError(f"no Deployments found in namespace {settings.k8s_namespace!r} "
                               f"at {settings.prometheus_url}; is the cluster up (up.ps1)?")
        history = self.telemetry.history(names, settings.live_warmup_minutes, settings.live_scrape_seconds)
        min_rows = int(settings.live_min_warmup_minutes * 60 / settings.live_scrape_seconds)
        null_rows = 2 * self.cfg.quarantine_silent
        for name in names:
            rows = history.get(name, [])
            if len(rows) < min_rows:
                logger.warning("live: skipping %s, only %d warm-up rows (need %d)", name, len(rows), min_rows)
                continue
            if len(rows) < null_rows:
                logger.warning("live: %s warms up on %d rows; per service null floors need %d, "
                               "running without them", name, len(rows), null_rows)
            self.services[name] = self._build_live(name, rows)
            self.warm_up_rows = max(self.warm_up_rows, len(rows))
            logger.info("fleet: %s warmed up on %d live rows", name, len(rows))
        if not self.services:
            raise RuntimeError("live: no service had enough Prometheus history to warm up")

    def _build_live(self, name: str, rows: list[dict]) -> ServiceRuntime:
        outbox, changes = Outbox(), QueueChangeEventSource()
        mgr = DynamicModelManager(name, self.cfg, self.hst_cfg,
                                  registry=MirroredRegistry(name, outbox),
                                  change_source=changes, publisher=outbox)
        mgr.warm_up(rows)
        rt = ServiceRuntime(service_id=name, display_name=display_name(name),
                            entity=f"{settings.k8s_namespace}/{name}", manager=mgr,
                            changes=changes, outbox=outbox, test_rows=[], test_df=pd.DataFrame(),
                            medians={})
        rt.rng.seed(name)
        return rt

    def process_row(self, rt: ServiceRuntime, x: dict):
        res = rt.manager.process(x)
        display = normalized_score(rt.manager, res.score)
        rt.last_display, rt.last_alarm = display, res.alarm
        rt.scores.append((res.step, round(display, 4), bool(res.alarm)))
        return x, res, display

    def process(self, rt: ServiceRuntime):  # replay-style stepping makes no sense without a scrape
        raise RuntimeError("live fleet: rows come from Prometheus scrapes (Runtime._live_loop)")

    def inject(self, service_id: str, kind: str) -> dict:
        raise ValueError("synthetic injections are replay only; use /api/live/{service}/{action}")


class ChangeFanOut:
    """
    One KubernetesDeploymentWatcher for the namespace, routed to each service's own change
    source by the event's service id (the Deployment's `app` label). The watcher has a single
    queue for the whole namespace, so it must not be given to the managers directly.
    """

    def __init__(self, namespace: str):
        from src.change_events import KubernetesDeploymentWatcher
        self.watcher = KubernetesDeploymentWatcher(namespace, service_label="app")
        self.started = False
        self._seen: dict[str, object] = {}         # service -> last routed Deployment generation

    def start(self) -> None:
        self.watcher.start()
        self.started = True

    def stop(self) -> None:
        if self.started:
            self.watcher.stop()

    def route(self, fleet: ServiceFleet) -> list:
        routed = []
        for evt in self.watcher.poll(0):
            rt = fleet.services.get(evt.service_id)
            if rt is None:
                continue
            # one rollout produces several MODIFIED watch events before the controller observes
            # it; route each Deployment generation once
            generation = evt.detail.get("generation")
            if generation is not None and self._seen.get(evt.service_id) == generation:
                continue
            self._seen[evt.service_id] = generation
            rt.changes.push(evt)
            routed.append(evt)
        return routed
