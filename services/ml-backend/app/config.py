"""
config.py — ml-backend settings (pydantic-settings, read from the environment or a .env file).

The defaults run the local demo stack: infrastructure/local/docker-compose.demo.yml (TimescaleDB on
5433, Redis 7 on 6380) and the ml-pipeline checkout next to this service. Either backing store may
be missing: the backend then keeps running on in-memory fallbacks (see app/store.py, app/bus.py).
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:selfheal@localhost:5433/selfheal"
    redis_url: str = "redis://localhost:6380"
    ml_pipeline_dir: Path = REPO_ROOT / "ml-pipeline"
    smd_dir: Path = REPO_ROOT / "datasets" / "smd"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Component 1 + 2 configuration (the final evaluated configuration, RESULTS_COMPONENT2.md)
    detector: str = "pca_s5"
    threshold_method: str = "pot"

    # Demo pacing. The lifecycle lengths are defined in "one day of samples"; here a day is
    # DEMO_SAMPLES_PER_DAY events and the replay plays REPLAY_EVENTS_PER_SEC events per service per
    # second, so a quarantine lasts ~24 s on stage. This is demo pacing, not the evaluated config.
    replay_events_per_sec: float = 40.0
    demo_samples_per_day: int = 960
    query_ttl_events: int = 12000         # ~5 minutes to answer an operator query on stage
    warm_up_rows: int = 6000              # SMD train rows per service used for the warm-up
    score_push_every: int = 10            # push one anomaly_score message every N events per service

    # Set false in tests to skip the replay loop and backing services.
    start_replay: bool = True
    use_backing_services: bool = True


settings = Settings()
