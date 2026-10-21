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
    # Sequential early stop: decide a quarantine at 50% or 75% of its length when the evidence is
    # already conclusive (a quiet champion, or a deployment repaired by re-baselining).
    cadal_early_stop: bool = True

    # Demo pacing. The lifecycle lengths are defined in "one day of samples"; here a day is
    # DEMO_SAMPLES_PER_DAY events and the replay plays REPLAY_EVENTS_PER_SEC events per service per
    # second, so a quarantine lasts ~24 s on stage. 1440 per day is SMD's own one sample a minute, so
    # the lifecycle runs the evaluated configuration, only replayed 60x faster than real time.
    replay_events_per_sec: float = 60.0
    demo_samples_per_day: int = 1440
    query_ttl_events: int = 18000         # ~5 minutes to answer an operator query on stage
    warm_up_rows: int = 6000              # SMD train rows per service used for the warm-up
    # Each service replays this many rows of its SMD test split, from the start row in
    # fleet.DEMO_SERVICES, forward then backward. The windows are label free stretches where the
    # warm-up model alarms at about its POT target, so a service stays calm until the presenter
    # injects something. 0 replays the whole test split once around, real anomalies included.
    replay_window_rows: int = 6000
    # Persisted metric rows: every Nth event per service, plus every alarming one. At 60 events/s
    # across six services, every event would be ~1 GB an hour (and is 60x the real rate anyway).
    persist_every: int = 10
    # Length of the demo "incident" injection in events (half a lifecycle day, ~12 s on stage). Shorter
    # spikes often never trip the drift detector on a quiet service, so nothing visible happens; a
    # whole day gets learned as a new normal. 0 means a fifth of a day.
    demo_incident_events: int = 720
    # Length of the demo "restart" blip: a rollout restart (deployment event) that disturbs the
    # service for a few minutes and then returns to its old normal (~4 s on stage).
    demo_restart_events: int = 240
    score_push_every: int = 10            # push one anomaly_score message every N events per service

    # Logs page: follow these containers' output (service name shown on the page -> container).
    follow_container_logs: bool = True
    log_containers: dict[str, str] = {"TimescaleDB": "selfheal-demo-timescaledb-1",
                                      "Redis": "selfheal-demo-redis-1"}
    log_http_access: bool = False         # also log every uvicorn access line (very chatty)

    # Telemetry source. "replay" (default) replays the SMD windows above; "prometheus" scores the
    # live Online Boutique on Kubernetes (infrastructure/online-boutique/up.ps1), with real
    # deployment events from the Kubernetes API and real faults from Chaos Mesh.
    telemetry_mode: str = "replay"
    prometheus_url: str = "http://localhost:9090"
    k8s_namespace: str = "online-boutique"
    live_scrape_seconds: float = 5.0
    # Accelerated pacing: one lifecycle "day" of evidence is this many minutes of live data
    # (30 min at a 5 s scrape = 360 samples), so a quarantine closes in 30 minutes, not a day.
    live_lifecycle_day_minutes: float = 30.0
    # Warm-up history pulled from Prometheus at start. Per-service null floors need two lifecycle
    # days of it (60 min); below that the lifecycle runs without them (logged).
    live_warmup_minutes: float = 60.0
    live_min_warmup_minutes: float = 10.0

    # Set false in tests to skip the replay loop and backing services.
    start_replay: bool = True
    use_backing_services: bool = True


settings = Settings()
