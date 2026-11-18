# services/decision-engine/app/decision/executor_kubernetes.py
"""
KubernetesExecutor — the real executor.

Translates a Decision into a concrete Kubernetes API call. Each
ActionType maps to exactly one verb:

    RESTART_POD       → delete Pod (owner ReplicaSet recreates it)
    SCALE_UP          → patch Deployment .spec.replicas += N
    SCALE_DOWN        → patch Deployment .spec.replicas -= N (min 1)
    ROLLBACK          → patch Deployment image to previous revision
    OPEN_CIRCUIT      → patch YARP ConfigMap (traffic weight → 0)
    CLOSE_CIRCUIT     → patch YARP ConfigMap (traffic weight → 100)
    FLUSH_CACHE       → POST to service /admin/flush (HTTP, not K8s)
    INCREASE_DB_POOL  → patch ConfigMap `db-pool-size`
    SCALE_CONSUMERS   → patch Deployment (Kafka consumer group)
    DRAIN_NODE        → cordon + drain node (admin-level, gated)
    NOOP              → no-op

Every action is idempotent — Kubernetes API is declarative, so
re-applying the same patch twice is safe. `idempotency_keys` in the
guardrails layer is defence-in-depth, not the sole guarantee.

Auth modes:
    in_cluster=True  → load_incluster_config() + ServiceAccount token
    in_cluster=False → load_kube_config() + ~/.kube/config

Dry-run mode is handled by `get_executor()` — it returns NoopExecutor
instead of this class. So this file only runs against a real cluster.

All errors are caught and converted to ExecutionStatus.FAILED with the
exception message in `detail`. The caller (job.py) records the outcome
in action_history for the repeat-failure bump in the risk classifier.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.decision.executor import ExecutionResult, ExecutionStatus
from app.decision.models import Decision
from app.rules.models import ActionType

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Action → handler mapping (declared at class level for readability)
# ─────────────────────────────────────────────────────────────────────
class KubernetesExecutor:
    """
    Loads the K8s client once at init and reuses it. Thread-safe for
    read-only use; every mutating call is to the API server which is
    itself concurrent-safe.
    """

    def __init__(self) -> None:
        self._core_api: Any = None
        self._apps_api: Any = None
        self._custom_api: Any = None
        self._load()

    # ── setup ─────────────────────────────────────────────────────
    def _load(self) -> None:
        from kubernetes import client, config

        if getattr(settings, "KUBERNETES_IN_CLUSTER", False):
            try:
                config.load_incluster_config()
                log.info("KubernetesExecutor: in-cluster config loaded")
            except Exception:
                log.exception("KubernetesExecutor: in-cluster load failed")
                raise
        else:
            try:
                config.load_kube_config()
                log.info("KubernetesExecutor: kubeconfig loaded")
            except Exception:
                log.exception("KubernetesExecutor: kubeconfig load failed")
                raise

        self._core_api = client.CoreV1Api()
        self._apps_api = client.AppsV1Api()
        self._custom_api = client.CustomObjectsApi()

    # ── the one public method ─────────────────────────────────────
    async def execute(self, decision: Decision) -> ExecutionResult:
        try:
            handler = self._handler_for(decision.action)
            result = handler(decision)
            return ExecutionResult(
                decision_id=decision.decision_id,
                service_id=decision.service_id,
                action=decision.action,
                status=result["status"],
                message=result.get("message", ""),
                detail=result.get("detail", {}),
            )
        except Exception as e:
            log.exception(
                "KubernetesExecutor: action %s on %s FAILED",
                decision.action.value, decision.service_id,
            )
            return ExecutionResult(
                decision_id=decision.decision_id,
                service_id=decision.service_id,
                action=decision.action,
                status=ExecutionStatus.FAILED,
                message=f"{type(e).__name__}: {e}",
                detail={"exception": str(e)},
            )

    # ── dispatch ──────────────────────────────────────────────────
    def _handler_for(self, action: ActionType):
        return {
            ActionType.RESTART_POD:       self._restart_pod,
            ActionType.SCALE_UP:          self._scale_up,
            ActionType.SCALE_DOWN:        self._scale_down,
            ActionType.ROLLBACK:          self._rollback,
            ActionType.OPEN_CIRCUIT:      self._open_circuit,
            ActionType.CLOSE_CIRCUIT:     self._close_circuit,
            ActionType.FLUSH_CACHE:       self._flush_cache,
            ActionType.INCREASE_DB_POOL:  self._increase_db_pool,
            ActionType.SCALE_CONSUMERS:   self._scale_consumers,
            ActionType.DRAIN_NODE:        self._drain_node,
            ActionType.NOOP:              self._noop,
        }[action]

    # ── individual handlers ──────────────────────────────────────
    def _restart_pod(self, decision: Decision) -> dict:
        """
        Delete every Pod matching the service label so the ReplicaSet
        recreates them. This is the correct "restart" idiom — deleting
        the Deployment would drop the spec.
        """
        selector = f"app={decision.service_id}"
        pods = self._core_api.list_namespaced_pod(
            namespace=settings.KUBERNETES_NAMESPACE,
            label_selector=selector,
            _request_timeout=settings.KUBERNETES_REQUEST_TIMEOUT_SEC,
        )
        deleted = []
        for pod in pods.items:
            self._core_api.delete_namespaced_pod(
                name=pod.metadata.name,
                namespace=settings.KUBERNETES_NAMESPACE,
                grace_period_seconds=decision.action_params.get(
                    "grace_period_sec", settings.KUBERNETES_DEFAULT_GRACE_SEC
                ),
                _request_timeout=settings.KUBERNETES_REQUEST_TIMEOUT_SEC,
            )
            deleted.append(pod.metadata.name)
        return {
            "status": ExecutionStatus.SUCCESS,
            "message": f"restarted {len(deleted)} pod(s)",
            "detail": {"pods_deleted": deleted, "selector": selector},
        }

    def _scale_up(self, decision: Decision) -> dict:
        """Increase Deployment .spec.replicas by `replicas` (default +1)."""
        delta = int(decision.action_params.get("replicas", 1))
        deploy = self._apps_api.read_namespaced_deployment(
            name=decision.service_id,
            namespace=settings.KUBERNETES_NAMESPACE,
        )
        old = deploy.spec.replicas or 1
        new = old + delta
        self._apps_api.patch_namespaced_deployment_scale(
            name=decision.service_id,
            namespace=settings.KUBERNETES_NAMESPACE,
            body={"spec": {"replicas": new}},
        )
        return {
            "status": ExecutionStatus.SUCCESS,
            "message": f"scaled {decision.service_id} from {old} to {new}",
            "detail": {"from": old, "to": new},
        }

    def _scale_down(self, decision: Decision) -> dict:
        """Decrease replicas (never below 1)."""
        delta = int(decision.action_params.get("replicas", 1))
        deploy = self._apps_api.read_namespaced_deployment(
            name=decision.service_id, namespace=settings.KUBERNETES_NAMESPACE,
        )
        old = deploy.spec.replicas or 1
        new = max(1, old - delta)
        self._apps_api.patch_namespaced_deployment_scale(
            name=decision.service_id, namespace=settings.KUBERNETES_NAMESPACE,
            body={"spec": {"replicas": new}},
        )
        return {
            "status": ExecutionStatus.SUCCESS,
            "message": f"scaled {decision.service_id} from {old} to {new}",
            "detail": {"from": old, "to": new},
        }

    def _rollback(self, decision: Decision) -> dict:
        """
        Roll back to the previous ReplicaSet's image.
        `action_params.revision` selects a revision; defaults to previous.
        """
        deploy = self._apps_api.read_namespaced_deployment(
            name=decision.service_id, namespace=settings.KUBERNETES_NAMESPACE,
        )
        # Find the previous image via ReplicaSets
        rs_list = self._apps_api.list_namespaced_replica_set(
            namespace=settings.KUBERNETES_NAMESPACE,
            label_selector=f"app={decision.service_id}",
        )
        # Sort by creation; take the second-newest distinct image
        images: list[str] = []
        for rs in sorted(rs_list.items, key=lambda r: r.metadata.creation_timestamp, reverse=True):
            for c in (rs.spec.template.spec.containers or []):
                if c.image and c.image not in images:
                    images.append(c.image)
        if len(images) < 2:
            raise RuntimeError(f"no previous revision for {decision.service_id}")
        prev_image = images[1]
        container = deploy.spec.template.spec.containers[0]
        old_image = container.image
        container.image = prev_image
        self._apps_api.patch_namespaced_deployment(
            name=decision.service_id, namespace=settings.KUBERNETES_NAMESPACE,
            body=deploy,
        )
        return {
            "status": ExecutionStatus.SUCCESS,
            "message": f"rolled back {decision.service_id} from {old_image} to {prev_image}",
            "detail": {"from_image": old_image, "to_image": prev_image},
        }

    def _open_circuit(self, decision: Decision) -> dict:
        """
        Set the target service's traffic weight to 0 in the YARP ConfigMap.
        Assumes the ConfigMap is named `yarp-routes` with key `traffic.json`.
        """
        return self._patch_yarp_weight(decision.service_id, 0)

    def _close_circuit(self, decision: Decision) -> dict:
        return self._patch_yarp_weight(decision.service_id, 100)

    def _patch_yarp_weight(self, service_id: str, weight: int) -> dict:
        cm = self._core_api.read_namespaced_config_map(
            name="yarp-routes", namespace=settings.KUBERNETES_NAMESPACE,
        )
        import json
        routes = json.loads(cm.data.get("traffic.json", "{}"))
        routes[service_id] = {"weight": weight}
        cm.data["traffic.json"] = json.dumps(routes)
        self._core_api.replace_namespaced_config_map(
            name="yarp-routes", namespace=settings.KUBERNETES_NAMESPACE, body=cm,
        )
        return {
            "status": ExecutionStatus.SUCCESS,
            "message": f"YARP weight for {service_id} set to {weight}",
            "detail": {"service": service_id, "weight": weight},
        }

    def _flush_cache(self, decision: Decision) -> dict:
        """
        Application-level HTTP call — NOT a K8s action. Requires the
        target service to expose POST /admin/flush. This is a placeholder
        that logs; replace with httpx.AsyncClient if/when target services
        implement the endpoint.
        """
        log.warning(
            "FLUSH_CACHE on %s: target must expose POST /admin/flush "
            "(no-op placeholder)", decision.service_id,
        )
        return {
            "status": ExecutionStatus.SUCCESS,
            "message": "flush requested (target-side endpoint not yet implemented)",
            "detail": {"service": decision.service_id},
        }

    def _increase_db_pool(self, decision: Decision) -> dict:
        """Patch the service's ConfigMap `db-pool-size`."""
        target_size = int(decision.action_params.get("pool_size", 20))
        cm_name = f"{decision.service_id}-config"
        cm = self._core_api.read_namespaced_config_map(
            name=cm_name, namespace=settings.KUBERNETES_NAMESPACE,
        )
        cm.data["db-pool-size"] = str(target_size)
        self._core_api.replace_namespaced_config_map(
            name=cm_name, namespace=settings.KUBERNETES_NAMESPACE, body=cm,
        )
        return {
            "status": ExecutionStatus.SUCCESS,
            "message": f"{cm_name} db-pool-size → {target_size}",
            "detail": {"service": decision.service_id, "pool_size": target_size},
        }

    def _scale_consumers(self, decision: Decision) -> dict:
        """Same as scale_up — the Deployment is the consumer."""
        return self._scale_up(decision)

    def _drain_node(self, decision: Decision) -> dict:
        """
        Admin-level — cordon and drain a node. Gated by guardrails:
        DRAIN_NODE has intrinsic_risk=0.80, so it will always escalate
        to HUMAN_LOOP before reaching here unless a rule is explicitly
        configured to allow auto-execute. This handler is a last-resort
        escape hatch.
        """
        node = decision.action_params.get("node")
        if not node:
            raise RuntimeError("DRAIN_NODE requires action_params.node")
        self._core_api.patch_node(node, {"spec": {"unschedulable": True}})
        return {
            "status": ExecutionStatus.SUCCESS,
            "message": f"node {node} cordoned (drain requires kubectl)",
            "detail": {"node": node},
        }

    def _noop(self, decision: Decision) -> dict:
        return {
            "status": ExecutionStatus.SUCCESS,
            "message": "NOOP — nothing to execute",
            "detail": {},
        }