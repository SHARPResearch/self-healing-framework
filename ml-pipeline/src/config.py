"""
config.py — Centralised configuration for ml-pipeline.

All tunable constants live here. This module handles configuration for:
- Prometheus data collection
- River streaming pipeline
- Half-Space Trees model
- ADWIN drift detection
- Pipeline settings
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()


@dataclass(frozen=True)
class PrometheusConfig:
    """
    Prometheus connection configuration.
    """
    url: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    timeout: int = int(os.getenv("PROMETHEUS_TIMEOUT", "30"))
    
    # Metrics collection settings
    time_range: str = os.getenv("DATA_TIME_RANGE", "5m")
    step: str = os.getenv("DATA_STEP", "15s")
    service_name: str = os.getenv("RIVER_SERVICE_NAME", "default")


@dataclass(frozen=True)
class RiverCollectorConfig:
    """
    River streaming collector configuration.
    
    Settings for the data collection pipeline using River library.
    """
    service_name: str = os.getenv("RIVER_SERVICE_NAME", "default")
    batch_size: int = int(os.getenv("RIVER_BATCH_SIZE", "100"))
    poll_interval: int = int(os.getenv("RIVER_POLL_INTERVAL", "60"))  # seconds
    
    # Feature columns to collect
    feature_columns: tuple = (
        'cpu_usage',
        'memory_usage', 
        'request_latency',
        'error_rate',
        'network_io'
    )


@dataclass(frozen=True)
class HSTConfig:
    """
    Hyperparameters for the Half-Space Trees model.

    Tuning notes for the i7-1165G7:
      - n_trees=25, height=15 gives excellent accuracy without exceeding ~5ms per
        learn_one() call on this CPU. Tested up to n_trees=50 with no memory issues
        at 16 GB RAM.
      - window_size=250 at a 15s Prometheus scrape interval covers ≈ 62.5 minutes
        of history per service — enough for diurnal pattern detection.
    """
    n_trees: int = int(os.getenv("HST_N_TREES", "25"))
    height: int = int(os.getenv("HST_HEIGHT", "15"))
    window_size: int = int(os.getenv("HST_WINDOW_SIZE", "250"))
    seed: int = int(os.getenv("HST_SEED", "42"))


@dataclass(frozen=True)
class ADWINConfig:
    """
    ADWIN (Adaptive Windowing) drift detector configuration.

    delta=0.002 means a 0.2% false-positive rate on drift detection.
    Lower delta → less sensitive (fewer false alarms, may miss fast drifts).
    Higher delta → more sensitive (faster detection, more false alarms).

    For student experimentation: try delta=0.005 (faster detection) vs
    delta=0.001 (stricter) and compare drift counts on the same SMD entity.
    """
    delta: float = float(os.getenv("ADWIN_DELTA", "0.002"))


@dataclass(frozen=True)
class PipelineConfig:
    """
    Top-level pipeline settings.
    """
    # SMD dataset paths (if using SMD dataset)
    smd_entity: str = os.getenv("SMD_ENTITY", "machine-1-1")
    smd_raw_dir: str = os.getenv("SMD_RAW_DIR", "../datasets/smd/raw")
    smd_processed_dir: str = os.getenv("SMD_PROCESSED_DIR", "./data/smd/processed")
    
    # Model storage
    model_snapshot_dir: str = os.getenv("MODEL_SNAPSHOT_DIR", "./model_snapshots")
    score_output_dir: str = os.getenv("SCORE_OUTPUT_DIR", "./outputs/scores")
    
    # MLflow tracking
    mlflow_tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    
    # Logging
    log_every_n_steps: int = int(os.getenv("LOG_EVERY_N_STEPS", "500"))
    
    # Data collection settings
    data_time_range: str = os.getenv("DATA_TIME_RANGE", "5m")
    data_step: str = os.getenv("DATA_STEP", "15s")


@dataclass(frozen=True)
class AppConfig:
    """
    Master configuration class that aggregates all sub-configurations.
    """
    prometheus: PrometheusConfig = PrometheusConfig()
    river_collector: RiverCollectorConfig = RiverCollectorConfig()
    hst: HSTConfig = HSTConfig()
    adwin: ADWINConfig = ADWINConfig()
    pipeline: PipelineConfig = PipelineConfig()


# ── Module-level singletons ─────────────────────────────────────────────────────
# These are safe for standalone use. In the FastAPI monorepo, these would be
# instantiated once in the lifespan() context manager and stored in app.state.*

# Individual configs (for backwards compatibility)
PROMETHEUS_CFG = PrometheusConfig()
RIVER_COLLECTOR_CFG = RiverCollectorConfig()
HST_CFG = HSTConfig()
ADWIN_CFG = ADWINConfig()
PIPELINE_CFG = PipelineConfig()

# Master config (recommended)
APP_CONFIG = AppConfig()


class _ConfigProxy:
    """Compatibility proxy so `from src.config import config` works with uppercase or attribute access."""
    def __init__(self, app_config: AppConfig):
        self._app_config = app_config

    @property
    def PROMETHEUS_URL(self) -> str:
        return self._app_config.prometheus.url

    @property
    def PROMETHEUS_TIMEOUT(self) -> int:
        return self._app_config.prometheus.timeout

    @property
    def RIVER_SERVICE_NAME(self) -> str:
        return self._app_config.river_collector.service_name

    @property
    def RIVER_BATCH_SIZE(self) -> int:
        return self._app_config.river_collector.batch_size

    @property
    def RIVER_POLL_INTERVAL(self) -> int:
        return self._app_config.river_collector.poll_interval

    @property
    def DATA_TIME_RANGE(self) -> str:
        return self._app_config.pipeline.data_time_range

    @property
    def DATA_STEP(self) -> str:
        return self._app_config.pipeline.data_step

    def __getattr__(self, item: str):
        if hasattr(self._app_config, item):
            return getattr(self._app_config, item)
        raise AttributeError(f"Config has no attribute '{item}'")


config = _ConfigProxy(APP_CONFIG)


# ── Helper functions ───────────────────────────────────────────────────────────

def get_config_dict() -> dict:
    """
    Get all configuration as a dictionary for logging/debugging.
    """
    return {
        'prometheus': {
            'url': PROMETHEUS_CFG.url,
            'timeout': PROMETHEUS_CFG.timeout,
            'time_range': PROMETHEUS_CFG.time_range,
            'step': PROMETHEUS_CFG.step,
            'service_name': PROMETHEUS_CFG.service_name,
        },
        'river_collector': {
            'service_name': RIVER_COLLECTOR_CFG.service_name,
            'batch_size': RIVER_COLLECTOR_CFG.batch_size,
            'poll_interval': RIVER_COLLECTOR_CFG.poll_interval,
            'feature_columns': list(RIVER_COLLECTOR_CFG.feature_columns),
        },
        'hst': {
            'n_trees': HST_CFG.n_trees,
            'height': HST_CFG.height,
            'window_size': HST_CFG.window_size,
            'seed': HST_CFG.seed,
        },
        'adwin': {
            'delta': ADWIN_CFG.delta,
        },
        'pipeline': {
            'smd_entity': PIPELINE_CFG.smd_entity,
            'model_snapshot_dir': PIPELINE_CFG.model_snapshot_dir,
            'score_output_dir': PIPELINE_CFG.score_output_dir,
            'mlflow_tracking_uri': PIPELINE_CFG.mlflow_tracking_uri,
            'log_every_n_steps': PIPELINE_CFG.log_every_n_steps,
        }
    }


def validate_config() -> bool:
    """
    Validate that the configuration is valid.
    
    Returns:
        True if valid, raises ValueError if invalid.
    """
    errors = []
    
    # Validate Prometheus URL
    if not PROMETHEUS_CFG.url.startswith(('http://', 'https://')):
        errors.append(f"Invalid PROMETHEUS_URL: {PROMETHEUS_CFG.url}")
    
    # Validate timeouts
    if PROMETHEUS_CFG.timeout < 1:
        errors.append(f"PROMETHEUS_TIMEOUT must be >= 1: {PROMETHEUS_CFG.timeout}")
    
    # Validate HST parameters
    if HST_CFG.n_trees < 1:
        errors.append(f"HST_N_TREES must be >= 1: {HST_CFG.n_trees}")
    
    if HST_CFG.height < 1:
        errors.append(f"HST_HEIGHT must be >= 1: {HST_CFG.height}")
    
    if HST_CFG.window_size < 10:
        errors.append(f"HST_WINDOW_SIZE must be >= 10: {HST_CFG.window_size}")
    
    # Validate ADWIN delta
    if not (0 < ADWIN_CFG.delta < 1):
        errors.append(f"ADWIN_DELTA must be between 0 and 1: {ADWIN_CFG.delta}")
    
    # Validate batch size
    if RIVER_COLLECTOR_CFG.batch_size < 1:
        errors.append(f"RIVER_BATCH_SIZE must be >= 1: {RIVER_COLLECTOR_CFG.batch_size}")
    
    # Validate poll interval
    if RIVER_COLLECTOR_CFG.poll_interval < 1:
        errors.append(f"RIVER_POLL_INTERVAL must be >= 1: {RIVER_COLLECTOR_CFG.poll_interval}")
    
    if errors:
        raise ValueError(f"Configuration validation failed:\n  - " + "\n  - ".join(errors))
    
    return True


def print_config():
    """
    Pretty print the current configuration.
    """
    import json
    print("=" * 60)
    print("Configuration Summary")
    print("=" * 60)
    print(json.dumps(get_config_dict(), indent=2, default=str))
    print("=" * 60)


# Auto-validate on import (optional)
if os.getenv("VALIDATE_CONFIG_ON_IMPORT", "true").lower() == "true":
    try:
        validate_config()
    except ValueError as e:
        import warnings
        warnings.warn(f"Configuration validation failed: {e}")