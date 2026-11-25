# services\decision-engine\app\config.py
"""
Central config. Reads from .env via python-dotenv.
Supports cloud-hosted Postgres (Neon), TimescaleDB (Tiger Cloud), Neo4j Aura.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the service root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Settings:
    # ── Anomaly DB (Neon Postgres) ─────────────────────────────
    ANOMALY_DB_URL: str = os.getenv("ANOMALY_DB_URL", "")

    # ── Telemetry DB (Tiger Cloud TimescaleDB) ─────────────────
    TELEMETRY_DB_URL: str = os.getenv("TELEMETRY_DB_URL", "")

    # ── Graph DB (Neo4j Aura) ──────────────────────────────────
    NEO4J_URI: str = os.getenv("NEO4J_URI", "")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # ── Ingestion tuning ───────────────────────────────────────
    TELEMETRY_POLL_INTERVAL_SEC: int = int(os.getenv("TELEMETRY_POLL_INTERVAL_SEC", "10"))
    ANOMALY_POLL_INTERVAL_SEC: int = int(os.getenv("ANOMALY_POLL_INTERVAL_SEC", "5"))
    RING_BUFFER_RETENTION_SEC: int = int(os.getenv("RING_BUFFER_RETENTION_SEC", "400"))
    SNAPSHOT_BEFORE_SEC: int = int(os.getenv("SNAPSHOT_BEFORE_SEC", "180"))
    SNAPSHOT_AFTER_SEC: int = int(os.getenv("SNAPSHOT_AFTER_SEC", "180"))

    # ── Decision pipeline ──────────────────────────────────────
    DECISION_POLL_INTERVAL_SEC: int = int(os.getenv("DECISION_POLL_INTERVAL_SEC", "10"))
    DECISION_WINDOW_SEC: int = int(os.getenv("DECISION_WINDOW_SEC", "300"))
    
    # ── Incident lifecycle ─────────────────────────────────────
    # How long a service must be healthy before its incident is closed.
    # Prevents flapping (unhealthy → healthy → unhealthy within 30s).
    INCIDENT_RECOVERY_HOLD_SEC: int = int(os.getenv("INCIDENT_RECOVERY_HOLD_SEC", "30"))
    
    # ── Internal telemetry source (mock endpoints on our own app) ──
    TELEMETRY_SOURCE_URL: str = os.getenv("TELEMETRY_SOURCE_URL", "http://localhost:8000")

    # ── Component 1 (ml-backend: anomaly detector + dynamic model updating) ──
    # Read-only. Anomaly signals and model state are pulled from here; when it is
    # unreachable the engine falls back to its local sources instead of stalling.
    COMPONENT1_URL: str = os.getenv("COMPONENT1_URL", "http://localhost:8002")

    # ── Developer convenience ──────────────────────────────────────
    # Auto-open the Swagger UI in the default browser when the server
    # boots. Set OPEN_DOCS=0 to disable (e.g. in prod/CI).
    OPEN_DOCS: bool = os.getenv("OPEN_DOCS", "1").lower() not in ("0", "false", "no")
    DOCS_BASE_URL: str = os.getenv("DOCS_BASE_URL", "http://localhost:8000")

    # ── Email notifications (SMTP) ─────────────────────────────────
    # Sending account, e.g. aquacore.it@gmail.com with a Gmail App Password.
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", ""))
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "1").lower() not in ("0", "false", "no")
    # Master switch — a missing SMTP_PASSWORD forces dry-run (log only).
    NOTIFY_ENABLED: bool = os.getenv("NOTIFY_ENABLED", "1").lower() not in ("0", "false", "no")
    NOTIFY_RECIPIENT: str = os.getenv("NOTIFY_RECIPIENT", "dinildulneth123@gmail.com")
    NOTIFY_ON_ANOMALY: bool = os.getenv("NOTIFY_ON_ANOMALY", "1").lower() not in ("0", "false", "no")
    NOTIFY_ON_DECISION: bool = os.getenv("NOTIFY_ON_DECISION", "1").lower() not in ("0", "false", "no")
    NOTIFY_ON_EXECUTION: bool = os.getenv("NOTIFY_ON_EXECUTION", "1").lower() not in ("0", "false", "no")

    # ── Redis (optional — guardrails cache) ────────────────────
    # If empty, the guardrails fall back to an in-memory store.
    # Local: redis://localhost:6379/0
    # Cloud: rediss://default:PASSWORD@HOST:PORT
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # ── Escalation worker ──────────────────────────────────────
    ESCALATION_POLL_INTERVAL_SEC: int = int(os.getenv("ESCALATION_POLL_INTERVAL_SEC", "30"))
    
    # ── Shadow Mode observer ──────────────────────────────────
    SHADOW_OBSERVE_INTERVAL_SEC: int = int(os.getenv("SHADOW_OBSERVE_INTERVAL_SEC", "60"))
    SHADOW_MIN_AGE_SEC: int = int(os.getenv("SHADOW_MIN_AGE_SEC", "300"))
    SHADOW_MAX_WAIT_MIN: int = int(os.getenv("SHADOW_MAX_WAIT_MIN", "60"))
    
    # ── Kubernetes executor ───────────────────────────────────
    # dry_run: log the call, don't touch the cluster (default safe).
    # Explicit auth is required before any real cluster call is allowed.
    KUBERNETES_DRY_RUN: bool = os.getenv("KUBERNETES_DRY_RUN", "1").lower() not in ("0", "false", "no")
    KUBERNETES_NAMESPACE: str = os.getenv("KUBERNETES_NAMESPACE", "default")
    KUBERNETES_IN_CLUSTER: bool = os.getenv("KUBERNETES_IN_CLUSTER", "0").lower() in ("1", "true", "yes")
    KUBERNETES_ALLOW_IN_CLUSTER: bool = os.getenv("KUBERNETES_ALLOW_IN_CLUSTER", "0").lower() in ("1", "true", "yes")
    KUBERNETES_KUBECONFIG_PATH: str = os.getenv("KUBERNETES_KUBECONFIG_PATH", "")
    KUBERNETES_API_SERVER: str = os.getenv("KUBERNETES_API_SERVER", "")
    KUBERNETES_AUTH_TOKEN: str = os.getenv("KUBERNETES_AUTH_TOKEN", "")
    KUBERNETES_CA_CERT_PATH: str = os.getenv("KUBERNETES_CA_CERT_PATH", "")
    KUBERNETES_REQUEST_TIMEOUT_SEC: int = int(os.getenv("KUBERNETES_REQUEST_TIMEOUT_SEC", "20"))
    KUBERNETES_DEFAULT_GRACE_SEC: int = int(os.getenv("KUBERNETES_DEFAULT_GRACE_SEC", "30"))
    
    def validate(self):
        """Fail-fast if any required secret is missing."""
        missing = []
        if not self.ANOMALY_DB_URL:
            missing.append("ANOMALY_DB_URL")
        if not self.TELEMETRY_DB_URL:
            missing.append("TELEMETRY_DB_URL")
        if not self.NEO4J_URI or not self.NEO4J_PASSWORD:
            missing.append("NEO4J_URI / NEO4J_PASSWORD")
        if missing:
            raise RuntimeError(
                f"Missing required env vars: {', '.join(missing)}. "
                f"Check services/decision-engine/.env"
            )


settings = Settings()