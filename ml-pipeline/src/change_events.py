"""
change_events.py — Component 2: exogenous change signals for the event-based update trigger.

A "change event" is something that happened to the monitored service outside the telemetry
itself (a Deployment rollout, a ConfigMap/HPA change, a scaling event) and is therefore prior
evidence that a following shift in behaviour may be a *new normal* rather than an incident.
The lifecycle manager (src/lifecycle_manager.py) uses these both as a trigger (open a validity
check immediately rather than waiting for ADWIN) and as attribution evidence (a shift that
follows a change needs less persistence before it is accepted as concept drift).

Sources:
  - ReplayChangeEventSource: deterministic, step-indexed events for offline experiments on SMD
    (which has no deployment log of its own), see src/data_pipeline.py drift scenarios.
  - KubernetesDeploymentWatcher: translates apps/v1 Deployment watch events into ChangeEvents.
    The translation (`change_event_from_k8s`) is pure and unit tested; the watch loop needs a
    reachable cluster and the optional `kubernetes` package and is not exercised by the tests.
"""

import logging
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChangeEvent:
    """One exogenous change to a monitored service."""
    service_id: str
    kind: str                       # "deployment", "config", "scale", ...
    step: Optional[int] = None      # stream position, used by replayed (offline) events
    timestamp: Optional[datetime] = None
    detail: dict = field(default_factory=dict, hash=False, compare=False)

    @property
    def event_id(self) -> str:
        where = self.step if self.step is not None else (
            self.timestamp.isoformat() if self.timestamp else "unknown"
        )
        return f"{self.service_id}:{self.kind}@{where}"


class ChangeEventSource(Protocol):
    def poll(self, step: int) -> list[ChangeEvent]:
        """Return change events that became visible at or before `step` and were not returned yet."""
        ...


class NullChangeEventSource:
    """No exogenous signal at all (the ablation without change awareness)."""

    def poll(self, step: int) -> list[ChangeEvent]:
        return []


class ReplayChangeEventSource:
    """Step-indexed change events replayed alongside an offline telemetry stream."""

    def __init__(self, events: Iterable[ChangeEvent]):
        self._pending = sorted(events, key=lambda e: e.step if e.step is not None else -1)

    def poll(self, step: int) -> list[ChangeEvent]:
        due = []
        while self._pending and (self._pending[0].step or 0) <= step:
            due.append(self._pending.pop(0))
        return due


def change_event_from_k8s(watch_event: dict, service_label: str = "app") -> Optional[ChangeEvent]:
    """
    Translate one Kubernetes watch event on an apps/v1 Deployment into a ChangeEvent.

    Only spec changes count as a rollout: Kubernetes bumps metadata.generation on every spec
    change (new image, env, resources) but not on status-only updates, so a MODIFIED event is a
    rollout only when generation moved past status.observedGeneration. Scale-only changes are
    reported as kind="scale" because they shift load per pod without changing code.
    """
    obj = watch_event.get("object") or {}
    meta = obj.get("metadata") or {}
    spec = obj.get("spec") or {}
    status = obj.get("status") or {}
    labels = meta.get("labels") or {}
    service_id = labels.get(service_label) or meta.get("name")
    if not service_id:
        return None

    event_type = watch_event.get("type")
    generation = meta.get("generation")
    observed = status.get("observedGeneration")
    annotations = meta.get("annotations") or {}

    if event_type == "ADDED" and observed is None:
        kind = "deployment"
    elif event_type == "MODIFIED" and generation is not None and observed is not None \
            and generation > observed:
        prev_replicas = annotations.get("selfheal.io/last-replicas")
        replicas = spec.get("replicas")
        kind = "scale" if prev_replicas is not None and str(replicas) != prev_replicas else "deployment"
    else:
        return None

    images = [
        c.get("image")
        for c in (((spec.get("template") or {}).get("spec") or {}).get("containers") or [])
    ]
    return ChangeEvent(
        service_id=service_id,
        kind=kind,
        timestamp=datetime.now(timezone.utc),
        detail={
            "namespace": meta.get("namespace"),
            "deployment": meta.get("name"),
            "generation": generation,
            "images": images,
        },
    )


class KubernetesDeploymentWatcher:
    """
    Background watch on Deployments in one namespace, buffering ChangeEvents for poll().

    poll() ignores `step` and returns whatever arrived since the last call, which is the
    live-system equivalent of ReplayChangeEventSource. Requires `pip install kubernetes`.
    """

    def __init__(self, namespace: str, service_label: str = "app"):
        self.namespace = namespace
        self.service_label = service_label
        self._queue: "queue.Queue[ChangeEvent]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        try:
            from kubernetes import client, config, watch
        except ImportError as exc:
            raise RuntimeError("KubernetesDeploymentWatcher needs the `kubernetes` package") from exc
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        api = client.AppsV1Api()

        def _run():
            w = watch.Watch()
            while not self._stop.is_set():
                for raw in w.stream(api.list_namespaced_deployment, self.namespace, timeout_seconds=30):
                    evt = change_event_from_k8s(
                        {"type": raw["type"], "object": api.api_client.sanitize_for_serialization(raw["object"])},
                        self.service_label,
                    )
                    if evt is not None:
                        logger.info("Change event observed: %s", evt.event_id)
                        self._queue.put(evt)
                    if self._stop.is_set():
                        break

        self._thread = threading.Thread(target=_run, name="k8s-deployment-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def poll(self, step: int) -> list[ChangeEvent]:
        out = []
        while True:
            try:
                out.append(self._queue.get_nowait())
            except queue.Empty:
                return out
