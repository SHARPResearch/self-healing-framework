"""
config.py — Centralised configuration for Component 1-2 pipeline.

All tunable constants live here. When this module is lifted into the FastAPI
monorepo, this class will be replaced by the project's Pydantic Settings class
(services/ml-backend/app/config.py), which reads the same env var names.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()  # loads .env file from project root


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
    n_trees: int = int(os.getenv("HST_N_TREES", 25))
    height: int = int(os.getenv("HST_HEIGHT", 15))
    window_size: int = int(os.getenv("HST_WINDOW_SIZE", 250))
    seed: int = 42


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
    delta: float = float(os.getenv("ADWIN_DELTA", 0.002))


@dataclass(frozen=True)
class PipelineConfig:
    """Top-level pipeline settings."""
    smd_entity: str = os.getenv("SMD_ENTITY", "machine-1-1")
    smd_raw_dir: str = os.getenv("SMD_RAW_DIR", "./data/smd/raw")
    smd_processed_dir: str = os.getenv("SMD_PROCESSED_DIR", "./data/smd/processed")
    model_snapshot_dir: str = os.getenv("MODEL_SNAPSHOT_DIR", "./model_snapshots")
    score_output_dir: str = os.getenv("SCORE_OUTPUT_DIR", "./outputs/scores")
    mlflow_tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "./mlruns")
    log_every_n_steps: int = int(os.getenv("LOG_EVERY_N_STEPS", 500))


# ── Module-level singletons (safe for standalone use) ─────────────────────────
# In the FastAPI monorepo, these are instantiated once in the lifespan()
# context manager and stored in app.state.*
HST_CFG = HSTConfig()
ADWIN_CFG = ADWINConfig()
PIPELINE_CFG = PipelineConfig()