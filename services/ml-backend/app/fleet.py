"""
fleet.py — the monitored services: one CADAL lifecycle manager per service.

Each demo service of the frontend (auth, orders, inventory, ...) replays the telemetry of one real
SMD server (Su et al., KDD 2019; 38 metrics, one sample per minute). Every service gets its own
DynamicModelManager from ml-pipeline with the final evaluated configuration: smoothed PCA detector,
POT-calibrated thresholds, CADAL attribution with re-baselining, the change-licensed retrain rule,
operator queries, and asynchronous decisions. Only the lifecycle lengths are rescaled
(LifecycleConfig.for_sampling) so a quarantine lasts seconds on stage instead of a day.

Demo injections (what the presenter clicks):
  deploy         a release shifts the baseline of 30% of the metrics, announced by a deployment
                 change event (the case CADAL repairs on its own)
  silent_change  an unannounced change to how a third of the metrics behave (level and spread):
                 nothing explains it, re-baselining cannot repair it, so CADAL asks the operator
  incident       a 20-second fault on a few metrics: alarmed, held, never learned
"""

import logging
import random
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Optional

import app.core.pipeline_path  # noqa: F401  (puts ml-pipeline on sys.path)
import numpy as np
import pandas as pd
from preprocess import preprocess_entity
from src.change_events import ChangeEvent, QueueChangeEventSource
from src.data_pipeline import make_scenario
from src.hst_model import classify_severity, detector_config
from src.lifecycle_manager import DynamicModelManager, LifecycleConfig
from src.mlflow_lifecycle import InMemoryRegistry

from app.config import settings

logger = logging.getLogger(__name__)

DEMO_SERVICES = [
    # (service_id, display name, SMD entity it replays, first test row of its replay window)
    ("service-a-auth", "Auth Service", "machine-2-9", 0),
    ("service-b-orders", "Orders Service", "machine-3-10", 15250),
    ("service-c-inventory", "Inventory Service", "machine-1-2", 9250),
    ("service-d-shipping", "Shipping Service", "machine-2-8", 0),
    ("service-e-payments", "Payments Service", "machine-2-2", 0),
    ("service-f-search", "Search Service", "machine-1-5", 0),
]
CANONICAL = ("cpu_rate", "memory_used", "network_rx", "network_tx", "disk_io_read", "disk_io_write")


class Outbox:
    """Collects lifecycle events and registry changes on the serving thread for the replay loop."""

    def __init__(self):
        self.events: deque = deque()

    def publish_lifecycle(self, payload: dict) -> None:  # src.publishers.EventPublisher
        self.events.append(("lifecycle", payload))


class MirroredRegistry(InMemoryRegistry):
    """The in-memory registry, with every transition and version change copied to the outbox."""

    def __init__(self, service_id: str, outbox: Outbox):
        super().__init__(service_id)
        self.outbox = outbox

    def _record(self, step, transition, from_v, to_v, reason, evidence=None):
        rec = super()._record(step, transition, from_v, to_v, reason, evidence)
        self.outbox.events.append(("transition", {
            "service_id": self.entity_id, "seq": rec.seq, "step": step, "transition": transition,
            "from_version": from_v, "to_version": to_v, "reason": reason,
            "evidence": rec.evidence}))
        for v in {from_v, to_v} - {None}:
            if v in self._versions:
                mv = self._versions[v]
                self.outbox.events.append(("version", {
                    "service_id": self.entity_id, "version": mv.version, "status": mv.status,
                    "threshold": mv.threshold, "kind": mv.tags.get("kind"),
                    "verdict": mv.tags.get("verdict"), "reason": mv.reason,
                    "created_step": mv.created_step, "tags": mv.tags}))
        return rec


@dataclass
class Injection:
    kind: str
    features: tuple
    deltas: tuple
    scales: tuple = ()
    until_step: Optional[int] = None     # None: persists (a new regime)


@dataclass
class ServiceRuntime:
    service_id: str
    display_name: str
    entity: str
    manager: DynamicModelManager
    changes: QueueChangeEventSource
    outbox: Outbox
    test_rows: list
    test_df: pd.DataFrame
    medians: dict
    cursor: int = 0
    injections: list = field(default_factory=list)
    scores: deque = field(default_factory=lambda: deque(maxlen=600))   # (step, normalized, alarm)
    last_display: float = 0.0
    last_alarm: bool = False
    last_action: Optional[str] = None
    last_action_at: Optional[str] = None
    drift_flag: bool = False
    rng: random.Random = field(default_factory=random.Random)


def lifecycle_config() -> LifecycleConfig:
    base = LifecycleConfig(policy="cadal", threshold_method=settings.threshold_method,
                           operator_queries=True, async_decisions=True)
    demo = base.for_sampling(settings.demo_samples_per_day)
    return replace(demo, query_ttl=settings.query_ttl_events, query_budget=3)


def normalized_score(mgr: DynamicModelManager, score: float) -> float:
    """
    The detector's score on the dashboard's scale: 0.5 is the version's calibrated alarm threshold,
    so the frontend's severity bands (watch < 0.5 <= warn < 0.7 <= degrade < 0.85 <= critical) mean
    the same thing for every service and every model version. Ratios are taken on the detector's
    raw error scale (PCA's SPE) when it has one.
    """
    unsquash = getattr(mgr.model, "unsquash", None)
    s, t = (unsquash(score), unsquash(mgr.threshold)) if unsquash else (score, mgr.threshold)
    if t <= 0:
        return 0.0
    return float(min(1.0, 0.5 * s / t))


class ServiceFleet:
    def __init__(self, services=DEMO_SERVICES, warm_up_rows: Optional[int] = None):
        self.services: dict[str, ServiceRuntime] = {}
        self.specs = services
        self.warm_up_rows = warm_up_rows or settings.warm_up_rows
        self.hst_cfg = detector_config(settings.detector)
        self.cfg = lifecycle_config()

    # -- set-up ------------------------------------------------------------------------------------
    def build(self) -> None:
        for service_id, name, entity, *start in self.specs:
            self.services[service_id] = self._build_service(service_id, name, entity, *start)
            logger.info("fleet: %s warmed up on %s", service_id, entity)

    def _build_service(self, service_id, name, entity, start: int = 0) -> ServiceRuntime:
        train = pd.read_parquet(preprocess_entity(entity, "train"))
        test = pd.read_parquet(preprocess_entity(entity, "test"))
        if settings.replay_window_rows:
            test = test.iloc[start:start + settings.replay_window_rows].reset_index(drop=True)
        outbox, changes = Outbox(), QueueChangeEventSource()
        mgr = DynamicModelManager(service_id, self.cfg, self.hst_cfg,
                                  registry=MirroredRegistry(service_id, outbox),
                                  change_source=changes, publisher=outbox)
        mgr.warm_up(train.tail(self.warm_up_rows).to_dict(orient="records"))
        rt = ServiceRuntime(service_id=service_id, display_name=name, entity=entity, manager=mgr,
                            changes=changes, outbox=outbox,
                            test_rows=test.to_dict(orient="records"), test_df=test,
                            medians=train.median().to_dict())
        rt.rng.seed(service_id)
        return rt

    # -- one replay step ---------------------------------------------------------------------------
    def next_row(self, rt: ServiceRuntime) -> dict:
        # Ping-pong through the replay window (forward, then backward) so an endless replay has
        # no wrap-around jump that would itself look like a regime change.
        n = len(rt.test_rows)
        i = rt.cursor % max(1, 2 * n - 2)
        x = dict(rt.test_rows[i if i < n else 2 * n - 2 - i])
        rt.cursor += 1
        step = rt.manager.step + 1
        rt.injections = [i for i in rt.injections if i.until_step is None or step <= i.until_step]
        for inj in rt.injections:
            for k, f in enumerate(inj.features):
                if inj.scales:
                    x[f] = rt.medians[f] + (x[f] - rt.medians[f]) * inj.scales[k] + inj.deltas[k]
                else:
                    x[f] = x[f] + inj.deltas[k]
                if inj.kind == "incident":
                    x[f] += rt.rng.gauss(0, 0.08)
        return x

    def process(self, rt: ServiceRuntime):
        x = self.next_row(rt)
        res = rt.manager.process(x)
        display = normalized_score(rt.manager, res.score)
        rt.last_display, rt.last_alarm = display, res.alarm
        rt.scores.append((res.step, round(display, 4), bool(res.alarm)))
        return x, res, display

    # -- demo controls -----------------------------------------------------------------------------
    def inject(self, service_id: str, kind: str) -> dict:
        rt = self.services[service_id]
        step = rt.manager.step + 1
        seed = len(rt.injections) + step
        if kind == "deploy":
            inj = make_scenario("deploy", rt.test_df, service_id, seed=seed, starts=(0.0,))[0]
            rt.injections.append(Injection("deploy", inj.features, inj.deltas))
            event = ChangeEvent(service_id, "deployment", step=step,
                                detail={"source": "demo", "features": list(inj.features)})
            rt.changes.push(event)
            return {"kind": kind, "change_event_id": event.event_id, "features": list(inj.features)}
        if kind == "silent_change":
            inj = make_scenario("silent", rt.test_df, service_id, seed=seed, starts=(0.0,),
                                feature_fraction=0.35)[0]
            scales = tuple(round(rt.rng.uniform(2.5, 3.5), 3) for _ in inj.features)
            deltas = tuple(round(d * 0.5, 4) for d in inj.deltas)
            rt.injections.append(Injection("silent_change", inj.features, deltas, scales))
            return {"kind": kind, "features": list(inj.features)}
        if kind == "incident":
            varying = [c for c in rt.test_df.columns if float(rt.test_df[c].std()) > 1e-6]
            feats = tuple(rt.rng.sample(varying, max(2, len(varying) // 8)))
            # a transient spike: a fifth of a lifecycle day, well inside one quarantine
            length = max(60, settings.demo_samples_per_day // 5)
            rt.injections.append(Injection("incident", feats, tuple(0.45 for _ in feats),
                                           until_step=step + length))
            return {"kind": kind, "features": list(feats), "events": length}
        raise ValueError(f"unknown injection {kind!r}")

    # -- views -------------------------------------------------------------------------------------
    def severity(self, rt: ServiceRuntime) -> str:
        return classify_severity(rt.last_display)

    def snapshot_features(self, x: dict) -> dict:
        return {k: round(float(x[k]), 5) for k in CANONICAL if k in x}

    def score_history(self, rt: ServiceRuntime, n: int = 20) -> list[float]:
        scores = [s for _, s, _ in rt.scores]
        if len(scores) <= n:
            return scores
        idx = np.linspace(0, len(scores) - 1, n).astype(int)
        return [scores[i] for i in idx]
