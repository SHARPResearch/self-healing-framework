"""
live_actions.py — real scenarios on the live Online Boutique (live mode's demo buttons, and the
chaos campaign). Each one changes the real cluster; nothing is injected into the telemetry.

  rollout        patch the Deployment's pod template (an annotation), which starts a real rolling
                 update. The Kubernetes watcher sees the new generation and sends a deployment
                 change event, so this exercises CADAL's change-aware path.
  traffic_up     triple the load generator's users. Every service's traffic shifts with no
                 deployment event on any of them: a real silent change.
  traffic_reset  put the load generator back to its baseline users.
  cpu_stress     Chaos Mesh StressChaos, CPU, on one pod (an incident, must not be learned)
  memory_stress  Chaos Mesh StressChaos, memory, on one pod
  pod_kill       Chaos Mesh PodChaos pod-kill on one pod
  network_delay  Chaos Mesh NetworkChaos, 200 ms delay on one pod

Uses the current kubeconfig context (up.ps1 makes it "sharp").
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

CHAOS_GROUP, CHAOS_VERSION = "chaos-mesh.org", "v1alpha1"
FAULTS = ("cpu_stress", "memory_stress", "pod_kill", "network_delay")
ACTIONS = ("rollout", "traffic_up", "traffic_reset") + FAULTS
BASE_USERS = 10
TRAFFIC_FACTOR = 3


class LiveActions:
    def __init__(self, namespace: str, fault_seconds: int = 180):
        from kubernetes import client, config

        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self.apps = client.AppsV1Api()
        self.custom = client.CustomObjectsApi()
        self.namespace = namespace
        self.fault_seconds = fault_seconds

    # -- deployments -------------------------------------------------------------------------------
    def rollout(self, service: str) -> dict:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        patch = {"spec": {"template": {"metadata": {"annotations": {"sharp.io/release": stamp}}}}}
        self.apps.patch_namespaced_deployment(service, self.namespace, patch)
        return {"action": "rollout", "service": service, "release": stamp}

    def _set_users(self, users: int) -> dict:
        dep = self.apps.read_namespaced_deployment("loadgenerator", self.namespace)
        containers = dep.spec.template.spec.containers
        main = next(c for c in containers if c.name == "main") if any(c.name == "main" for c in containers) else containers[0]
        env = [{"name": e.name, "value": e.value} for e in (main.env or []) if e.value_from is None]
        env = [e for e in env if e["name"] != "USERS"] + [{"name": "USERS", "value": str(users)}]
        patch = {"spec": {"template": {"spec": {"containers": [{"name": main.name, "env": env}]}}}}
        self.apps.patch_namespaced_deployment("loadgenerator", self.namespace, patch)
        return {"action": "traffic", "users": users}

    def traffic_up(self, service: Optional[str] = None) -> dict:
        return {**self._set_users(BASE_USERS * TRAFFIC_FACTOR), "action": "traffic_up"}

    def traffic_reset(self, service: Optional[str] = None) -> dict:
        return {**self._set_users(BASE_USERS), "action": "traffic_reset"}

    # -- chaos -------------------------------------------------------------------------------------
    def _chaos(self, kind: str, plural: str, service: str, spec: dict, tag: str) -> dict:
        # object names must be RFC 1123 (no underscores); the label keeps the action's own name
        name = f"sharp-{tag.replace('_', '-')}-{service}-{int(time.time())}"[:63].rstrip("-")
        body = {"apiVersion": f"{CHAOS_GROUP}/{CHAOS_VERSION}", "kind": kind,
                "metadata": {"name": name, "namespace": self.namespace,
                             "labels": {"sharp.io/fault": tag, "sharp.io/service": service}},
                "spec": {"mode": "one",
                         "selector": {"namespaces": [self.namespace], "labelSelectors": {"app": service}},
                         **spec}}
        self.custom.create_namespaced_custom_object(CHAOS_GROUP, CHAOS_VERSION, self.namespace, plural, body)
        return {"action": tag, "service": service, "chaos": name, "seconds": self.fault_seconds}

    def cpu_stress(self, service: str) -> dict:
        return self._chaos("StressChaos", "stresschaos", service,
                           {"stressors": {"cpu": {"workers": 2, "load": 90}},
                            "duration": f"{self.fault_seconds}s"}, "cpu_stress")

    def memory_stress(self, service: str) -> dict:
        return self._chaos("StressChaos", "stresschaos", service,
                           {"stressors": {"memory": {"workers": 1, "size": "256MB"}},
                            "duration": f"{self.fault_seconds}s"}, "memory_stress")

    def pod_kill(self, service: str) -> dict:
        return self._chaos("PodChaos", "podchaos", service, {"action": "pod-kill"}, "pod_kill")

    def network_delay(self, service: str) -> dict:
        return self._chaos("NetworkChaos", "networkchaos", service,
                           {"action": "delay", "delay": {"latency": "200ms", "jitter": "20ms"},
                            "duration": f"{self.fault_seconds}s"}, "network_delay")

    def run(self, action: str, service: str) -> dict:
        if action not in ACTIONS:
            raise ValueError(f"unknown live action {action!r}; expected one of {ACTIONS}")
        return getattr(self, action)(service)

    def cleanup(self) -> int:
        """Delete every chaos object SHARP created (finished ones stay around otherwise)."""
        removed = 0
        for plural in ("stresschaos", "podchaos", "networkchaos"):
            items = self.custom.list_namespaced_custom_object(
                CHAOS_GROUP, CHAOS_VERSION, self.namespace, plural, label_selector="sharp.io/fault")
            for item in items.get("items", []):
                self.custom.delete_namespaced_custom_object(
                    CHAOS_GROUP, CHAOS_VERSION, self.namespace, plural, item["metadata"]["name"])
                removed += 1
        return removed
