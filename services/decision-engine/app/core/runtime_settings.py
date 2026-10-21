"""
Runtime-editable engine settings.

Every tunable knob the operator can change at runtime lives here as a SPEC
entry. Values are persisted in the `engine_settings` table (Neon) and, on
load, are written back onto the `settings` singleton so the rest of the
codebase keeps reading `settings.X` exactly as before.

Resolution order for an effective value:
    DB override  >  .env value  >  coded default (from SPEC)

`update()` validates, persists, audits, then re-applies live:
    * interval knobs  → reschedule the APScheduler job
    * ring buffer     → mutate the retention window

Premium gating: some knobs are marked `premium=True`. A non-premium actor
cannot change them (the route layer passes the actor's plan in).

The scheduler is injected once at startup (see main.py) so apply() can
reschedule jobs without importing main (avoids a circular import).
"""
from __future__ import annotations

import logging
from datetime import timezone, timedelta
from typing import Any, Callable

from app.config import settings
from app.persistence.postgres import postgres_store

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# SPEC — the single source of truth for what is tunable.
#
#   key         : the settings attribute name (settings.<key>)
#   type        : "int" | "bool" | "str"
#   default     : coded fallback if neither DB nor env provide a value
#   min/max     : inclusive bounds (int only)
#   live        : True when the value takes effect without a restart
#   premium     : True when only a premium actor may change it
#   group       : UI grouping
#   label/help  : human-facing copy
#   apply       : optional callable(key, value, ctx) → applied live
# ─────────────────────────────────────────────────────────────────────
SETTINGS_SPEC: dict[str, dict[str, Any]] = {
    "TELEMETRY_POLL_INTERVAL_SEC": {
        "type": "int", "default": 10, "min": 1, "max": 600, "live": True,
        "premium": False, "group": "Ingestion",
        "label": "Telemetry poll interval",
        "help": "How often the mock telemetry is pulled into the ring buffer.",
    },
    "ANOMALY_POLL_INTERVAL_SEC": {
        "type": "int", "default": 5, "min": 1, "max": 600, "live": True,
        "premium": False, "group": "Ingestion",
        "label": "Anomaly poll interval",
        "help": "How often the engine checks for new anomaly events.",
    },
    "RING_BUFFER_RETENTION_SEC": {
        "type": "int", "default": 400, "min": 30, "max": 3600, "live": True,
        "premium": False, "group": "Ingestion",
        "label": "Ring buffer retention",
        "help": "How much recent telemetry history the in-memory buffer keeps.",
    },
    "SNAPSHOT_BEFORE_SEC": {
        "type": "int", "default": 30, "min": 5, "max": 1800, "live": False,
        "premium": True, "group": "Snapshots",
        "label": "Snapshot window (before)",
        "help": "Telemetry captured BEFORE an anomaly is detected. Premium.",
    },
    "SNAPSHOT_AFTER_SEC": {
        "type": "int", "default": 30, "min": 5, "max": 1800, "live": False,
        "premium": True, "group": "Snapshots",
        "label": "Snapshot window (after)",
        "help": "Telemetry captured AFTER an anomaly is detected. Premium.",
    },
    "DECISION_POLL_INTERVAL_SEC": {
        "type": "int", "default": 10, "min": 1, "max": 600, "live": True,
        "premium": False, "group": "Decision pipeline",
        "label": "Decision poll interval",
        "help": "How often new anomalies are evaluated against the rule set.",
    },
    "DECISION_WINDOW_SEC": {
        "type": "int", "default": 300, "min": 30, "max": 86400, "live": True,
        "premium": True, "group": "Decision pipeline",
        "label": "Decision lookback window",
        "help": "Only anomalies within this window are decided. Premium.",
    },
    "INCIDENT_RECOVERY_HOLD_SEC": {
        "type": "int", "default": 30, "min": 5, "max": 3600, "live": False,
        "premium": True, "group": "Incident lifecycle",
        "label": "Incident recovery hold",
        "help": "A service must stay healthy this long before an incident closes. Premium.",
    },
    # ── Notifications (not rescheduled, read live each send) ────
    "NOTIFY_ENABLED": {
        "type": "bool", "default": True, "live": True,
        "premium": False, "group": "Notifications",
        "label": "Email notifications",
        "help": "Send email when an anomaly is detected and when a decision is made.",
    },
    "NOTIFY_RECIPIENT": {
        "type": "str", "default": "dinildulneth123@gmail.com", "live": True,
        "premium": False, "group": "Notifications",
        "label": "Notify recipient",
        "help": "End-user address that receives anomaly / decision emails.",
    },
    "NOTIFY_ON_ANOMALY": {
        "type": "bool", "default": True, "live": True,
        "premium": True, "group": "Notifications",
        "label": "Email on anomaly detected",
        "help": "Send an email the moment a new incident opens. Premium.",
    },
    "NOTIFY_ON_DECISION": {
        "type": "bool", "default": True, "live": True,
        "premium": True, "group": "Notifications",
        "label": "Email on decision made",
        "help": "Send an email with the chosen action after each decision. Premium.",
    },
}


# Keys reschedulable without a restart. The value is the id of the
# existing APScheduler job that must be re-registered.
_RESCHEDULE_MAP: dict[str, str] = {
    "TELEMETRY_POLL_INTERVAL_SEC": "telemetry_puller",
    "ANOMALY_POLL_INTERVAL_SEC": "anomaly_poller",
    "DECISION_POLL_INTERVAL_SEC": "decision_pipeline",
}


class RuntimeSettings:
    _instance: "RuntimeSettings | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._overrides: dict[str, Any] = {}
            cls._instance._scheduler = None
            cls._instance._applied_at = None
        return cls._instance

    # ── wiring ────────────────────────────────────────────────────
    def bind_scheduler(self, scheduler) -> None:
        """Called once from the lifespan so apply() can reschedule jobs."""
        self._scheduler = scheduler

    # ── load / read ───────────────────────────────────────────────
    async def load(self) -> int:
        """
        Read persisted overrides and apply them onto the settings singleton.
        Returns the number of overrides applied.
        """
        try:
            overrides = await postgres_store.list_settings()
        except Exception:
            log.exception("RuntimeSettings: could not read overrides — using env/defaults")
            overrides = {}
        self._overrides = overrides or {}
        for key in SETTINGS_SPEC:
            self._apply_to_settings(key, self._effective(key))
        log.info("RuntimeSettings loaded (%d override(s))", len(self._overrides))
        return len(self._overrides)

    async def reload(self) -> int:
        return await self.load()

    def _env_value(self, key: str) -> Any:
        """Raw value the settings singleton currently holds (env or default)."""
        return getattr(settings, key, None)

    def _effective(self, key: str) -> Any:
        """DB override if present, else the current settings value, else default."""
        if key in self._overrides:
            return self._overrides[key]
        current = self._env_value(key)
        if current is None:
            return SETTINGS_SPEC[key]["default"]
        return current

    def _source(self, key: str) -> str:
        if key in self._overrides:
            return "db"
        if getattr(settings, key, None) is not None:
            return "env"
        return "default"

    def get_all(self) -> list[dict]:
        """Everything the UI needs: effective value + metadata."""
        out: list[dict] = []
        for key, spec in SETTINGS_SPEC.items():
            out.append({
                "key": key,
                "value": self._coerce(key, self._effective(key)),
                "source": self._source(key),
                "type": spec["type"],
                "default": spec["default"],
                "min": spec.get("min"),
                "max": spec.get("max"),
                "live": spec.get("live", False),
                "premium": spec.get("premium", False),
                "group": spec.get("group", "General"),
                "label": spec.get("label", key),
                "help": spec.get("help", ""),
            })
        return out

    # ── write ─────────────────────────────────────────────────────
    def validate(self, key: str, value: Any) -> Any:
        """Return the coerced value or raise ValueError with a reason."""
        if key not in SETTINGS_SPEC:
            raise ValueError(f"unknown setting '{key}'")
        return self._coerce(key, value, strict=True)

    async def update(
        self,
        patch: dict[str, Any],
        actor: str = "unknown",
        is_premium: bool = True,
    ) -> dict:
        """
        Apply a {key: value} patch. Validates everything first (all-or-nothing),
        persists, audits, then applies live. Returns a summary.
        """
        if not patch:
            return {"ok": True, "changed": [], "requires_restart": [], "settings": self.get_all()}

        coerced: dict[str, Any] = {}
        errors: list[str] = []
        for key, raw in patch.items():
            if key not in SETTINGS_SPEC:
                errors.append(f"{key}: unknown setting")
                continue
            spec = SETTINGS_SPEC[key]
            if spec.get("premium") and not is_premium:
                errors.append(f"{key}: premium-only setting")
                continue
            try:
                coerced[key] = self._coerce(key, raw, strict=True)
            except ValueError as e:
                errors.append(f"{key}: {e}")

        if errors:
            raise ValueError("; ".join(errors))

        changed: list[str] = []
        requires_restart: list[str] = []
        for key, value in coerced.items():
            old = self._coerce(key, self._effective(key))
            if old == value:
                continue
            await postgres_store.save_setting(key, value, actor=actor)
            await postgres_store.save_settings_audit(key, old, value, actor=actor)
            self._overrides[key] = value
            self._apply_to_settings(key, value)
            applied_live = await self._apply_live(key, value)
            changed.append(key)
            if not applied_live:
                requires_restart.append(key)

        log.info(
            "RuntimeSettings updated by %s: %s%s",
            actor,
            ", ".join(changed) or "(no change)",
            f" — restart needed for {requires_restart}" if requires_restart else "",
        )
        return {
            "ok": True,
            "changed": changed,
            "requires_restart": requires_restart,
            "settings": self.get_all(),
        }

    # ── internals ─────────────────────────────────────────────────
    def _coerce(self, key: str, value: Any, strict: bool = False) -> Any:
        spec = SETTINGS_SPEC[key]
        t = spec["type"]
        try:
            if t == "int":
                v = int(value)
            elif t == "bool":
                if isinstance(value, bool):
                    v = value
                elif str(value).strip().lower() in ("1", "true", "yes", "on"):
                    v = True
                elif str(value).strip().lower() in ("0", "false", "no", "off"):
                    v = False
                else:
                    raise ValueError("expected a boolean")
            else:
                v = str(value)
        except (TypeError, ValueError) as e:
            if strict:
                raise ValueError(f"expected {t} ({e})")
            return spec["default"]

        if t == "int":
            lo, hi = spec.get("min"), spec.get("max")
            if lo is not None and v < lo:
                if strict:
                    raise ValueError(f"must be >= {lo}")
                return lo
            if hi is not None and v > hi:
                if strict:
                    raise ValueError(f"must be <= {hi}")
                return hi
        if t == "str" and spec.get("default") == "dinildulneth123@gmail.com":
            # recipient must look like an email
            if v and "@" not in v:
                if strict:
                    raise ValueError("must be a valid email address")
                return spec["default"]
        return v

    def _apply_to_settings(self, key: str, value: Any) -> None:
        """Write the effective value back onto the settings singleton."""
        try:
            setattr(settings, key, value)
        except Exception:
            log.exception("RuntimeSettings: failed to set settings.%s", key)

    async def _apply_live(self, key: str, value: Any) -> bool:
        """
        Apply a value that takes effect without a restart.
        Returns True if applied live, False if it needs a restart.
        """
        # Ring buffer — mutate the retention window directly.
        if key == "RING_BUFFER_RETENTION_SEC":
            try:
                from app.ingestion.ring_buffer import ring_buffer
                ring_buffer.retention = timedelta(seconds=value)
                return True
            except Exception:
                log.exception("RuntimeSettings: ring buffer apply failed")
                return False

        # Interval knobs — re-register the APScheduler job.
        job_id = _RESCHEDULE_MAP.get(key)
        if job_id:
            return self._reschedule(job_id)

        # Everything else is read live at use-site (notifications) or only
        # takes effect on the next cycle — no action needed.
        return SETTINGS_SPEC[key].get("live", False)

    def _reschedule(self, job_id: str) -> bool:
        if self._scheduler is None:
            log.warning("RuntimeSettings: no scheduler bound, cannot reschedule %s", job_id)
            return False
        try:
            if job_id == "telemetry_puller":
                from app.ingestion.telemetry_puller import start_telemetry_puller
                start_telemetry_puller(self._scheduler)
            elif job_id == "anomaly_poller":
                from app.ingestion.anomaly_sink import start_anomaly_sink
                start_anomaly_sink(self._scheduler)
            elif job_id == "decision_pipeline":
                from app.decision.job import start_decision_pipeline
                start_decision_pipeline(self._scheduler)
            else:
                return False
            return True
        except Exception:
            log.exception("RuntimeSettings: reschedule %s failed", job_id)
            return False


runtime_settings = RuntimeSettings()
