# services/decision-engine/app/decision/executor.py
"""
Execution interface — the seam between Decision and Reality.

Component 2 does NOT execute actions. It emits `Decision` records with a
`policy_outcome`. A downstream layer (Component 2's "Execution Layer",
Kubernetes API / YARP gateway) consumes those records and does the work.

This module defines that seam so the rest of the pipeline can be built
and tested today, and the real executor drops in later without touching
the decision code.

Two implementations ship:

    NoopExecutor      — logs the intent, records a synthetic SUCCESS.
                        Used in dev/test and until the K8s executor lands.

Future:
    KubernetesExecutor — patches Deployment / Pod / YARP via the
                         in-cluster ServiceAccount.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from app.decision.models import Decision
from app.rules.models import ActionType

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Execution result
# ─────────────────────────────────────────────────────────────────────
class ExecutionStatus(str, Enum):
    SUCCESS      = "SUCCESS"
    FAILED       = "FAILED"
    SKIPPED      = "SKIPPED"       # policy said do-not-execute
    DRY_RUN      = "DRY_RUN"       # shadow mode
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"  # NoopExecutor


@dataclass
class ExecutionResult:
    decision_id: str
    service_id: str
    action: ActionType
    status: ExecutionStatus
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "service_id": self.service_id,
            "action": self.action.value,
            "status": self.status.value,
            "message": self.message,
            "detail": self.detail,
            "executed_at": self.executed_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────
# Protocol — anything that can execute a decision
# ─────────────────────────────────────────────────────────────────────
@runtime_checkable
class Executor(Protocol):
    """
    The one method the pipeline calls. Implementations must be async.
    """
    async def execute(self, decision: Decision) -> ExecutionResult: ...


# ─────────────────────────────────────────────────────────────────────
# NoopExecutor — default implementation
# ─────────────────────────────────────────────────────────────────────
class NoopExecutor:
    """
    Logs the intended action and returns NOT_IMPLEMENTED so logs are
    honest (this decision was not actually carried out by a real system).

    Reads `decision.action` / `decision.action_params` / `decision.service_id`.
    Does not mutate anything.
    """

    async def execute(self, decision: Decision) -> ExecutionResult:
        log.info(
            "NoopExecutor: would execute %s on %s (decision=%s, policy=%s)",
            decision.action.value,
            decision.service_id,
            decision.decision_id,
            decision.policy_outcome.value if decision.policy_outcome else "UNKNOWN",
        )
        return ExecutionResult(
            decision_id=decision.decision_id,
            service_id=decision.service_id,
            action=decision.action,
            status=ExecutionStatus.NOT_IMPLEMENTED,
            message=(
                "No Kubernetes/YARP executor wired yet. "
                "This record documents the intended action only."
            ),
            detail={
                "action_params": decision.action_params,
                "policy_outcome": (
                    decision.policy_outcome.value if decision.policy_outcome else None
                ),
            },
        )


class AuthRequiredExecutor:
    async def execute(self, decision: Decision) -> ExecutionResult:
        log.warning(
            "AuthRequiredExecutor: refusing %s on %s; no user-supplied Kubernetes auth",
            decision.action.value,
            decision.service_id,
        )
        return ExecutionResult(
            decision_id=decision.decision_id,
            service_id=decision.service_id,
            action=decision.action,
            status=ExecutionStatus.SKIPPED,
            message="Kubernetes execution skipped: no user-supplied auth configured.",
            detail={
                "reason": "KUBERNETES_AUTH_REQUIRED",
                "action_params": decision.action_params,
                "policy_outcome": (
                    decision.policy_outcome.value if decision.policy_outcome else None
                ),
            },
        )

# Old One -----------------------------------------------------------
# # Module-level singleton — swap this out in `main.py` when the real
# # executor lands.
# executor: Executor = NoopExecutor()


# New One -----------------------------------------------------------

# ─────────────────────────────────────────────────────────────────────
# Factory — main.py calls this once at startup
# ─────────────────────────────────────────────────────────────────────
def kubernetes_auth_configured() -> bool:
    from app.config import settings

    if getattr(settings, "KUBERNETES_AUTH_TOKEN", "") and getattr(settings, "KUBERNETES_API_SERVER", ""):
        return True
    if getattr(settings, "KUBERNETES_KUBECONFIG_PATH", ""):
        return True
    if getattr(settings, "KUBERNETES_IN_CLUSTER", False) and getattr(settings, "KUBERNETES_ALLOW_IN_CLUSTER", False):
        return True
    return False


def get_executor() -> Executor:
    """
    Pick the executor based on dry-run and explicit Kubernetes auth.

    The import is lazy so tests that never touch Kubernetes don't pay
    the `kubernetes` package import cost.
    """
    from app.config import settings

    if getattr(settings, "KUBERNETES_DRY_RUN", True):
        log.info("Executor: NoopExecutor (KUBERNETES_DRY_RUN=true)")
        return NoopExecutor()

    if not kubernetes_auth_configured():
        log.warning(
            "Executor: AuthRequiredExecutor (set KUBERNETES_KUBECONFIG_PATH or "
            "KUBERNETES_API_SERVER + KUBERNETES_AUTH_TOKEN)"
        )
        return AuthRequiredExecutor()

    try:
        from app.decision.executor_kubernetes import KubernetesExecutor
        return KubernetesExecutor()
    except Exception:
        log.exception(
            "Executor: KubernetesExecutor unavailable — refusing execution"
        )
        return AuthRequiredExecutor()


# Kept for backwards compat with anything still importing the singleton.
executor: Executor = NoopExecutor()