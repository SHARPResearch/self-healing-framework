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