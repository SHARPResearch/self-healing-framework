"""
mlflow_lifecycle.py — Component 2 (Dynamic Model Updating): versioned model registry + audit trail.

Every model the lifecycle manager (src/lifecycle_manager.py) ever serves is a registered
version here: the warm-up model, each stable checkpoint, each promoted challenger. Every state
transition (register, promote, rollback, checkpoint) is an append-only TransitionRecord carrying
the step, wall-clock time, reason and the full attribution evidence (proposal FR4).

Two implementations behind one interface:

  InMemoryRegistry  fast local registry, also used directly by the offline evaluation so a
                    28-entity ablation is not dominated by MLflow I/O. Optionally appends every
                    transition to a JSONL audit file.
  MLflowRegistry    the same registry mirrored into MLflow: each version is a registered model
                    version (pyfunc, loadable with mlflow.pyfunc.load_model), the serving version
                    carries the `production` alias, superseded versions get status=archived tags,
                    and each transition is logged as a JSON artifact + metrics on the active run.
                    MLflow 3 deprecated the old "Production"/"Archived" registry *stages* the
                    proposal mentions; aliases + tags are their supported replacement.

Snapshots are src/hst_state.HSTState blobs (~13 KB for the tuned model) rather than pickles
(~71 MB), and rollback reads the local copy, never the network, so a rollback completes inside a
single scoring cycle (FR3). Replicas converge by calling `MLflowRegistry.sync_production()`
and applying the returned state to their own structurally identical model (FR5).
"""

import json
import logging
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from src.hst_state import HSTState

logger = logging.getLogger(__name__)

PRODUCTION_ALIAS = "production"


@dataclass
class ModelVersion:
    version: int
    state: HSTState
    threshold: float
    target_rate: float
    created_step: int
    reason: str
    status: str = "candidate"          # candidate | production | archived
    tags: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TransitionRecord:
    seq: int
    step: int
    wall_time: float
    transition: str                    # register | promote | rollback | checkpoint
    from_version: Optional[int]
    to_version: Optional[int]
    reason: str
    evidence: dict = field(default_factory=dict)


class InMemoryRegistry:
    """Local versioned registry with an append-only transition log."""

    def __init__(self, entity_id: str, audit_path: Optional[str | Path] = None):
        self.entity_id = entity_id
        self._versions: dict[int, ModelVersion] = {}
        self._production: Optional[int] = None
        self._production_history: list[int] = []
        self.transitions: list[TransitionRecord] = []
        self._audit_path = Path(audit_path) if audit_path else None
        if self._audit_path:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)

    # ── reads ────────────────────────────────────────────────────────────────
    @property
    def production_version(self) -> Optional[int]:
        return self._production

    def get(self, version: int) -> ModelVersion:
        return self._versions[version]

    def production(self) -> ModelVersion:
        if self._production is None:
            raise LookupError(f"[{self.entity_id}] no production model registered yet")
        return self._versions[self._production]

    def previous_production(self) -> Optional[ModelVersion]:
        """The production version served before the current one, i.e. the rollback target."""
        if len(self._production_history) < 2:
            return None
        return self._versions[self._production_history[-2]]

    @property
    def versions(self) -> list[ModelVersion]:
        return [self._versions[v] for v in sorted(self._versions)]

    # ── writes ───────────────────────────────────────────────────────────────
    def _record(self, step, transition, from_v, to_v, reason, evidence=None) -> TransitionRecord:
        rec = TransitionRecord(
            seq=len(self.transitions), step=step, wall_time=time.time(), transition=transition,
            from_version=from_v, to_version=to_v, reason=reason, evidence=dict(evidence or {}),
        )
        self.transitions.append(rec)
        if self._audit_path:
            with open(self._audit_path, "a") as f:
                f.write(json.dumps({"entity_id": self.entity_id, **asdict(rec)}) + "\n")
        logger.info("[%s] %s v%s -> v%s at step %d: %s",
                    self.entity_id, transition, from_v, to_v, step, reason)
        return rec

    def register(
        self, state: HSTState, threshold: float, target_rate: float, *,
        step: int, reason: str, tags: Optional[dict] = None,
    ) -> int:
        version = len(self._versions) + 1
        self._versions[version] = ModelVersion(
            version=version, state=state, threshold=threshold, target_rate=target_rate,
            created_step=step, reason=reason, tags=dict(tags or {}),
        )
        self._record(step, "register", None, version, reason, {"threshold": threshold, **(tags or {})})
        return version

    def set_production(
        self, version: int, *, step: int, transition: str, reason: str,
        evidence: Optional[dict] = None,
    ) -> None:
        """Point production at `version`, archiving the version it replaces."""
        previous = self._production
        if previous is not None and previous != version:
            self._versions[previous].status = "archived"
        self._versions[version].status = "production"
        self._production = version
        self._production_history.append(version)
        self._record(step, transition, previous, version, reason, evidence)

    def checkpoint(self, state: HSTState, threshold: float, target_rate: float, *, step: int,
                   reason: str) -> int:
        """Register the current healthy production state as a new stable version and serve it."""
        version = self.register(state, threshold, target_rate, step=step, reason=reason,
                                tags={"kind": "stable_checkpoint"})
        self.set_production(version, step=step, transition="checkpoint", reason=reason)
        return version


class MLflowRegistry(InMemoryRegistry):
    """
    InMemoryRegistry mirrored into the MLflow model registry and the active MLflow run.

    Expects the caller to have an active run (mlflow.start_run) for transition logging; model
    versions are registered under `hst-<entity_id>`.
    """

    def __init__(self, entity_id: str, tracking_uri: str, audit_path: Optional[str | Path] = None,
                 hst_params: Optional[dict] = None, feature_names: Optional[list[str]] = None,
                 with_scaler: bool = True):
        super().__init__(entity_id, audit_path)
        import mlflow
        from mlflow.tracking import MlflowClient

        self._mlflow = mlflow
        mlflow.set_tracking_uri(tracking_uri)
        self._client = MlflowClient(tracking_uri=tracking_uri)
        self.model_name = f"hst-{entity_id}"
        self._hst_params = dict(hst_params or {})
        self._feature_names = list(feature_names or [])
        self._with_scaler = with_scaler
        self._mlflow_version: dict[int, str] = {}

    def register(self, state, threshold, target_rate, *, step, reason, tags=None) -> int:
        version = super().register(state, threshold, target_rate, step=step, reason=reason, tags=tags)
        from src.hst_pyfunc import HSTStatePyfunc

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.bin"
            state_path.write_bytes(state.to_bytes())
            config_path = Path(tmp) / "config.json"
            config_path.write_text(json.dumps({
                "hst_params": self._hst_params,
                "feature_names": self._feature_names,
                "with_scaler": self._with_scaler,
                "threshold": threshold,
                "target_rate": target_rate,
            }))
            info = self._mlflow.pyfunc.log_model(
                name=f"hst_v{version}",
                python_model=HSTStatePyfunc(),
                artifacts={"state": str(state_path), "config": str(config_path)},
                pip_requirements=["river==0.25.0", "mlflow"],
            )
        mv = self._mlflow.register_model(info.model_uri, self.model_name)
        self._mlflow_version[version] = mv.version
        all_tags = {"local_version": version, "threshold": threshold, "target_rate": target_rate,
                    "created_step": step, "reason": reason, "status": "candidate", **(tags or {})}
        for k, v in all_tags.items():
            self._client.set_model_version_tag(self.model_name, mv.version, k, str(v))
        return version

    def set_production(self, version, *, step, transition, reason, evidence=None) -> None:
        previous = self._production
        super().set_production(version, step=step, transition=transition, reason=reason,
                               evidence=evidence)
        if previous is not None and previous != version:
            self._client.set_model_version_tag(
                self.model_name, self._mlflow_version[previous], "status", "archived")
        mlv = self._mlflow_version[version]
        self._client.set_model_version_tag(self.model_name, mlv, "status", "production")
        self._client.set_registered_model_alias(self.model_name, PRODUCTION_ALIAS, mlv)

        rec = self.transitions[-1]
        self._mlflow.log_dict(asdict(rec), f"transitions/{rec.seq:04d}_{rec.transition}.json")
        self._mlflow.log_metrics(
            {"production_version": version, f"transition_{transition}": 1}, step=step)
        self._mlflow.set_tag("production_version", str(version))

    def sync_production(self) -> tuple[str, HSTState, float]:
        """
        Fetch whatever MLflow currently marks as production (FR5: replicas share no memory).

        Returns (mlflow_version, state, threshold); the caller applies the state to its own
        model with src.hst_state.apply().
        """
        mv = self._client.get_model_version_by_alias(self.model_name, PRODUCTION_ALIAS)
        local = Path(self._mlflow.artifacts.download_artifacts(f"models:/{self.model_name}@{PRODUCTION_ALIAS}"))
        state = HSTState.from_bytes((local / "artifacts" / "state.bin").read_bytes())
        config = json.loads((local / "artifacts" / "config.json").read_text())
        return mv.version, state, float(config["threshold"])
