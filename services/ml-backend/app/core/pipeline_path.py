"""
pipeline_path.py — make ml-pipeline importable as the single source of truth.

The anomaly detector, the CADAL lifecycle and the registry live in ml-pipeline/src and are imported
from there (`from src.lifecycle_manager import ...`), not copied into this service, so the backend
always runs exactly the code the evaluation measured. datasets/smd provides the SMD loader the
demo replays from.
"""

import sys

from app.config import settings


def ensure_pipeline_on_path() -> None:
    for path in (settings.ml_pipeline_dir, settings.smd_dir):
        p = str(path)
        if p not in sys.path:
            sys.path.insert(0, p)


ensure_pipeline_on_path()
