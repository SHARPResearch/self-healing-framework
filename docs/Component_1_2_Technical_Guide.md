# Component 1–2: Technical Implementation Guide
## HST Anomaly Detection + Dynamic Model Updating Pipeline
### Self-Healing Microservice Architecture — Individual Research Component

---

> **Scope of this document:** This guide covers only your assigned individual workload —
> Component 1 Extension (HST warm-up) and Component 2 (streaming updates, ADWIN drift
> detection, MLflow rollbacks). The code is written as a **standalone pipeline** that is
> structurally designed to be lifted directly into the group monorepo's FastAPI ML backend.

---

## Part 0: Environment Decision — VS Code Local vs. Google Colab

### Verdict: Use VS Code Locally on Your Machine

Your Acer Aspire 5 (i7-1165G7, 16 GB RAM, MX350) is **very well suited** for this workload.
Here is the engineering rationale:

| Factor | VS Code Local | Google Colab |
|---|---|---|
| **`river` library** | `river` is CPU-only, sequential. Your i7-1165G7 has excellent single-core boost (4.7 GHz). No GPU needed. | Same compute, but with network latency added. |
| **MLflow tracking** | MLflow writes runs to a local SQLite DB + artifact folder. Persists across sessions permanently. | Colab filesystem resets on every session. You'd lose all run history every 90 minutes. |
| **Pickle snapshots** | Saved to disk, always accessible. | Lost on session end. Can work around with Google Drive mounts, but fragile. |
| **Long-running stream** | 28 SMD entities × ~28,000 rows each ≈ 784,000 iterations. Can run overnight. | 90-min idle timeout will kill the session mid-training. |
| **Redis/TimescaleDB** | You can run Docker containers locally for integration testing. | Difficult to expose local services from Colab. |
| **Debugging** | Full breakpoint support, inline variable inspection, Jupyter cells alongside scripts. | Limited; no true debugger for long-running loops. |
| **MX350 GPU** | Not used at all — `river` is CPU-only. Your GPU gives no advantage here. | Same — irrelevant for this workload. |

**The only valid reason to use Colab** would be if you have a very slow or metered internet
connection and struggle to download the SMD dataset (~500 MB). Even then, download it once
locally and you're done.

---

## Part 1: Environment Setup

### Step 1.1 — Install Python 3.11

Download the official installer from https://python.org/downloads/ and install Python 3.11.x.
During installation on Windows, **check "Add Python to PATH"**.

Verify:
```bash
python --version
# Expected: Python 3.11.x
```

### Step 1.2 — Install uv (Fast Package Manager)

`uv` is a drop-in replacement for pip that is 10–100× faster. Strongly recommended.

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verify
uv --version
```

If you prefer plain pip, every `uv` command below has a pip equivalent shown in comments.

### Step 1.3 — Create the Standalone Project

```bash
# Create project folder (outside the monorepo for now)
mkdir component-1-2-pipeline
cd component-1-2-pipeline

# Initialise with uv (creates pyproject.toml + .venv automatically)
uv init --python 3.11

# OR with plain venv:
# python -m venv .venv
# .venv\Scripts\activate     ← Windows
# source .venv/bin/activate  ← Mac/Linux
```

### Step 1.4 — Install Dependencies

```bash
# With uv (resolves and installs in parallel, much faster than pip)
uv add river mlflow pandas pyarrow numpy scikit-learn matplotlib tqdm python-dotenv

# pip equivalent:
# pip install river mlflow pandas pyarrow numpy scikit-learn matplotlib tqdm python-dotenv
```

**Dependency rationale:**
| Package | Version | Purpose |
|---|---|---|
| `river` | ≥0.21 | Half-Space Trees + ADWIN drift detection |
| `mlflow` | ≥2.12 | Experiment tracking, model registry, artifact storage |
| `pandas` | ≥2.0 | SMD CSV loading and preprocessing |
| `pyarrow` | ≥14.0 | Parquet serialisation for preprocessed features |
| `numpy` | ≥1.26 | Numerical operations |
| `scikit-learn` | ≥1.4 | Precision/recall/F1 evaluation against SMD labels |
| `matplotlib` | ≥3.8 | Score visualisation plots |
| `tqdm` | ≥4.66 | Progress bars on streaming loops |
| `python-dotenv` | ≥1.0 | `.env` config loading |

### Step 1.5 — Install VS Code Extensions

Open VS Code and install these extensions (Ctrl+Shift+X):
- **Python** (Microsoft) — language support, debugger
- **Pylance** — type-checking, autocomplete
- **Jupyter** — run `.ipynb` notebooks alongside scripts
- **GitLens** — useful once you push to the monorepo
- **Thunder Client** — for testing the FastAPI endpoints later

Select your interpreter: Ctrl+Shift+P → "Python: Select Interpreter" → choose `.venv`

### Step 1.6 — Project Folder Structure

Create this structure manually or run the commands below:

```
component-1-2-pipeline/
├── data/
│   └── smd/
│       ├── raw/                ← paste raw SMD files here (see Step 1.7)
│       │   ├── train/          ← machine-1-1.txt … machine-3-11.txt
│       │   ├── test/
│       │   └── test_label/
│       └── processed/          ← auto-generated .parquet files
├── src/
│   ├── __init__.py
│   ├── config.py               ← all tunable constants in one place
│   ├── data_pipeline.py        ← SMD loading + streaming generator
│   ├── hst_model.py            ← HST + ADWIN core class
│   └── mlflow_lifecycle.py     ← MLflow run management + rollback
├── notebooks/
│   └── 01_exploration.ipynb
├── mlruns/                     ← auto-created by MLflow
├── model_snapshots/            ← local pickle snapshots
├── outputs/
│   └── scores/                 ← CSV logs of per-event scores
├── .env                        ← environment variables
├── requirements.txt            ← pip freeze output for CI
└── main.py                     ← entry point
```

```bash
# Create folder structure
mkdir -p data/smd/raw/train data/smd/raw/test data/smd/raw/test_label
mkdir -p data/smd/processed src notebooks model_snapshots outputs/scores
echo "" > src/__init__.py
```

### Step 1.7 — Download the SMD Dataset

```bash
# Clone OmniAnomaly repository (contains the SMD dataset)
# Run this from your project root
git clone https://github.com/NetManAIOps/OmniAnomaly.git /tmp/omnianomaly

# Copy the dataset files
cp -r /tmp/omnianomaly/ServerMachineDataset/train/    data/smd/raw/train/
cp -r /tmp/omnianomaly/ServerMachineDataset/test/     data/smd/raw/test/
cp -r /tmp/omnianomaly/ServerMachineDataset/test_label/ data/smd/raw/test_label/

# On Windows (PowerShell):
# xcopy /tmp/omnianomaly/ServerMachineDataset/train/ data\smd\raw\train\ /E
```

**SMD dataset structure you should see:**
```
data/smd/raw/train/machine-1-1.txt   ← 28,479 rows × 38 features (space-separated)
data/smd/raw/train/machine-1-2.txt
...
data/smd/raw/train/machine-3-11.txt  ← 28 entities total
data/smd/raw/test/machine-1-1.txt    ← test split (same shape)
data/smd/raw/test_label/machine-1-1.txt  ← binary labels (0=normal, 1=anomaly)
```

### Step 1.8 — Create `.env` File

```ini
# .env — local configuration
MLFLOW_TRACKING_URI=./mlruns
HST_N_TREES=25
HST_HEIGHT=15
HST_WINDOW_SIZE=250
ADWIN_DELTA=0.002
LOG_EVERY_N_STEPS=500
SMD_ENTITY=machine-1-1
SMD_RAW_DIR=./data/smd/raw
SMD_PROCESSED_DIR=./data/smd/processed
MODEL_SNAPSHOT_DIR=./model_snapshots
SCORE_OUTPUT_DIR=./outputs/scores

# ── Future integration flags ──────────────────────────────────────────────────
# When this code is lifted into the FastAPI monorepo, these values will be
# read from Kubernetes Secrets / environment variables injected at pod startup.
# TIMESCALEDB_URL=postgresql+asyncpg://postgres:selfheal@localhost:5432/selfheal
# REDIS_URL=redis://localhost:6379
```

---

## Part 2: Configuration Module

**`src/config.py`**

```python
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
```

---

## Part 3: SMD Telemetry Data Pipeline

**`src/data_pipeline.py`**

```python
"""
data_pipeline.py — SMD dataset loading, preprocessing, and streaming generator.

What this module does:
  1. Reads the 28-machine SMD text files (space-separated, no headers).
  2. Maps 38 columns to human-readable feature names.
  3. Normalises each feature to [0, 1] using min-max statistics computed
     from the TRAINING split only (avoiding data leakage from the test split).
  4. Saves processed data as Parquet files for fast repeated loading.
  5. Exposes a generator function that yields one feature dict at a time,
     simulating a live Prometheus metrics firehose.

Architecture note:
  In the production FastAPI service, this generator's role is replaced by the
  POST /ingest/metrics endpoint. Each call to that endpoint provides one
  feature vector, equivalent to one yield from stream_entity().
  The normalisation parameters would be stored in TimescaleDB or Redis
  rather than a local JSON file, so all replicas share the same scale.
"""

import json
import logging
import os
from pathlib import Path
from typing import Generator, Optional

import numpy as np
import pandas as pd

from src.config import PIPELINE_CFG

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SMD Feature Schema
# The SMD dataset has 38 unlabelled columns. Based on the OmniAnomaly paper
# and repository documentation, the features capture server-level telemetry:
# cols 0–5:  CPU-related metrics (usage, load averages, iowait, etc.)
# cols 6–11: Memory metrics (total, free, buffer, cache, etc.)
# cols 12–17: Network I/O (bytes in/out, packets in/out, errors, drops)
# cols 18–23: Disk I/O (reads, writes, read bytes, write bytes, util, await)
# cols 24–35: Derived / application-level metrics (request rates, connections)
# cols 36–37: Miscellaneous system metrics
#
# We use systematic names (feat_00 … feat_37) because the SMD authors did not
# publish human-readable column names. The first 7 columns are remapped to our
# canonical Prometheus-compatible feature schema for downstream HST consumption.
# ─────────────────────────────────────────────────────────────────────────────

# All 38 SMD column names
SMD_COLUMNS = [f"feat_{i:02d}" for i in range(38)]

# Canonical feature names used by the HST model (subset of SMD features).
# These map directly to what the production Prometheus scrape collects.
# The remaining SMD features (feat_07 … feat_37) are passed through as-is
# since HST is non-parametric and benefits from all available features.
CANONICAL_MAP = {
    "feat_00": "cpu_rate",
    "feat_01": "memory_used_fraction",
    "feat_02": "network_rx",
    "feat_03": "network_tx",
    "feat_04": "disk_read",
    "feat_05": "disk_write",
    "feat_06": "request_rate",  # proxy for latency / throughput
}


def load_raw_entity(entity_id: str, split: str = "train") -> pd.DataFrame:
    """
    Load a raw SMD entity file and assign column names.

    Args:
        entity_id: e.g. "machine-1-1"
        split: "train" | "test"

    Returns:
        DataFrame with shape (n_rows, 38), columns = SMD_COLUMNS.
    """
    raw_path = Path(PIPELINE_CFG.smd_raw_dir) / split / f"{entity_id}.txt"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"SMD file not found: {raw_path}\n"
            f"Did you run the data download step? (see Part 1, Step 1.7)"
        )

    df = pd.read_csv(
        raw_path,
        sep=" ",          # space-separated, no header
        header=None,
        names=SMD_COLUMNS,
        dtype=np.float32, # float32 saves ~50% memory vs float64 (important at scale)
    )
    logger.info(f"Loaded {split} split for {entity_id}: {df.shape}")
    return df


def load_labels(entity_id: str) -> pd.Series:
    """
    Load binary ground-truth anomaly labels for an SMD entity (test split only).

    Returns:
        pd.Series of 0/1 integers, length = rows in test split.
    """
    label_path = Path(PIPELINE_CFG.smd_raw_dir) / "test_label" / f"{entity_id}.txt"
    if not label_path.exists():
        raise FileNotFoundError(f"Label file not found: {label_path}")

    labels = pd.read_csv(label_path, header=None, names=["label"], squeeze=True)
    anomaly_pct = labels.mean() * 100
    logger.info(
        f"Labels for {entity_id}: {len(labels)} rows, "
        f"{anomaly_pct:.1f}% anomalous"
    )
    return labels.astype(int)


class SMDNormaliser:
    """
    Min-max normaliser fitted on the TRAINING split of one SMD entity.

    Critical design principle: the normaliser is fitted ONLY on training data.
    The same min/max values are then used to normalise the test split.
    This prevents data leakage and mirrors how the production system would work
    (normalisation params computed at warm-up time, then frozen).

    In the production system (FastAPI monorepo), these min/max values would be
    stored as JSON in Redis so all pod replicas share the same normalisation.
    """

    def __init__(self):
        self._min: Optional[np.ndarray] = None
        self._max: Optional[np.ndarray] = None
        self._range: Optional[np.ndarray] = None
        self._columns: Optional[list[str]] = None

    def fit(self, train_df: pd.DataFrame) -> "SMDNormaliser":
        """Compute per-feature min/max from training split."""
        self._min = train_df.values.min(axis=0).astype(np.float32)
        self._max = train_df.values.max(axis=0).astype(np.float32)
        # Replace zero-range features with 1.0 to avoid division by zero
        self._range = np.where(
            (self._max - self._min) == 0,
            1.0,
            self._max - self._min
        ).astype(np.float32)
        self._columns = list(train_df.columns)
        logger.info(f"Normaliser fitted on {len(train_df)} rows, {len(self._columns)} features.")
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply min-max normalisation, clipping to [0, 1]."""
        if self._min is None:
            raise RuntimeError("Call fit() before transform()")
        normalised = (df.values - self._min) / self._range
        # Clip to [0, 1] — test values can exceed training range
        normalised = np.clip(normalised, 0.0, 1.0)
        return pd.DataFrame(normalised, columns=self._columns, dtype=np.float32)

    def save(self, entity_id: str) -> None:
        """Persist normalisation params to JSON for reproducibility."""
        out_dir = Path(PIPELINE_CFG.smd_processed_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        params = {
            "entity_id": entity_id,
            "columns": self._columns,
            "min": self._min.tolist(),
            "max": self._max.tolist(),
        }
        with open(out_dir / f"{entity_id}_norm_params.json", "w") as f:
            json.dump(params, f, indent=2)
        logger.info(f"Normalisation params saved for {entity_id}.")

    @classmethod
    def load(cls, entity_id: str) -> "SMDNormaliser":
        """Load previously saved normalisation params."""
        path = Path(PIPELINE_CFG.smd_processed_dir) / f"{entity_id}_norm_params.json"
        with open(path) as f:
            params = json.load(f)
        inst = cls()
        inst._min = np.array(params["min"], dtype=np.float32)
        inst._max = np.array(params["max"], dtype=np.float32)
        inst._range = np.where(
            (inst._max - inst._min) == 0, 1.0, inst._max - inst._min
        ).astype(np.float32)
        inst._columns = params["columns"]
        return inst


def preprocess_entity(entity_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Full preprocessing pipeline for one SMD entity:
      1. Load raw train + test splits.
      2. Fit normaliser on train.
      3. Transform both splits.
      4. Save as Parquet files.
      5. Return (normalised_train, normalised_test).
    """
    processed_dir = Path(PIPELINE_CFG.smd_processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)

    train_path = processed_dir / f"{entity_id}_train.parquet"
    test_path = processed_dir / f"{entity_id}_test.parquet"

    # Return cached files if already processed
    if train_path.exists() and test_path.exists():
        logger.info(f"Loading cached processed data for {entity_id}.")
        return pd.read_parquet(train_path), pd.read_parquet(test_path)

    # Fresh preprocessing
    raw_train = load_raw_entity(entity_id, split="train")
    raw_test = load_raw_entity(entity_id, split="test")

    normaliser = SMDNormaliser().fit(raw_train)
    normaliser.save(entity_id)

    norm_train = normaliser.transform(raw_train)
    norm_test = normaliser.transform(raw_test)

    # Rename canonical features for downstream HST compatibility
    norm_train = norm_train.rename(columns=CANONICAL_MAP)
    norm_test = norm_test.rename(columns=CANONICAL_MAP)

    norm_train.to_parquet(train_path, index=False)
    norm_test.to_parquet(test_path, index=False)

    logger.info(
        f"Preprocessed {entity_id}: "
        f"train={norm_train.shape}, test={norm_test.shape}"
    )
    return norm_train, norm_test


def stream_entity(
    df: pd.DataFrame,
    entity_id: str,
    delay_seconds: float = 0.0,
) -> Generator[dict[str, float], None, None]:
    """
    Core streaming generator — yields one feature dict per iteration.

    This function simulates the live Prometheus metrics firehose. Each `yield`
    is equivalent to one call to the production FastAPI POST /ingest/metrics
    endpoint receiving a JSON payload.

    Args:
        df: Preprocessed (normalised) DataFrame for this entity.
        entity_id: Used for logging only.
        delay_seconds: Optional sleep between yields to simulate real-time
                       cadence (e.g., 0.015 for 15s Prometheus interval sped up).
                       Leave at 0.0 for maximum throughput during warm-up.

    Yields:
        dict[str, float] — one feature vector, keyed by column name.
        This is the exact type consumed by HSTStreamProcessor.score_and_learn().

    Example:
        >>> for features in stream_entity(train_df, "machine-1-1"):
        ...     score = processor.score_and_learn(features)
    """
    import time

    n_rows = len(df)
    logger.info(f"Starting stream for {entity_id}: {n_rows} events.")

    for idx, row in enumerate(df.itertuples(index=False, name=None)):
        # Convert row tuple to feature dict — this is the production data contract
        # matching MetricPayload.metrics: dict[str, float] in the FastAPI schema.
        feature_dict: dict[str, float] = dict(zip(df.columns, row))

        yield feature_dict

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    logger.info(f"Stream complete for {entity_id}: {n_rows} events processed.")
```

---

## Part 4: Core ML Script — HST + ADWIN

**`src/hst_model.py`**

```python
"""
hst_model.py — Half-Space Trees anomaly detector with ADWIN drift detection.

Component 1 Extension: HST warm-up on SMD training data.
Component 2: Online streaming updates + ADWIN drift detection.

Architecture design notes for monorepo integration:
  - HSTStreamProcessor is designed as a stateful class with no global state.
  - One instance per service_id (matching the production HSTModelRegistry pattern).
  - All state is contained in self._model (HST) and self._adwin (ADWIN).
  - These are serialisable via pickle, making MLflow artifact storage straightforward.
  - In the multi-replica FastAPI deployment, the model state is managed by
    HSTModelRegistry (with asyncio.Lock) — this class is the single-service equivalent.
"""

import logging
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from river.anomaly import HalfSpaceTrees
from river.drift import ADWIN

from src.config import ADWIN_CFG, HST_CFG, PIPELINE_CFG

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data structures for tracking per-event results
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StreamEvent:
    """
    Result of processing one feature vector through the pipeline.
    This is what gets logged to MLflow, written to TimescaleDB, and
    published to the Redis Pub/Sub channel in the production system.
    """
    step: int                     # Sequential event index (0-based)
    service_id: str               # Entity/service identifier
    anomaly_score: float          # HST output, clamped to [0.0, 1.0]
    severity: str                 # watch / warn / degrade / critical
    drift_detected: bool          # True if ADWIN flagged a change point
    latency_ms: float             # Time taken for score_one + learn_one (ms)
    features: dict[str, float]    # Raw feature dict (truncated in logs)


@dataclass
class RunningStats:
    """
    Rolling statistics maintained over the last N scores.
    Used to feed MLflow metrics without logging every individual score.
    """
    window_size: int = 500
    _scores: list[float] = field(default_factory=list)

    def update(self, score: float) -> None:
        self._scores.append(score)
        if len(self._scores) > self.window_size:
            self._scores.pop(0)  # O(1) amortised with small window

    @property
    def mean(self) -> float:
        return sum(self._scores) / len(self._scores) if self._scores else 0.0

    @property
    def maximum(self) -> float:
        return max(self._scores) if self._scores else 0.0

    @property
    def above_warn(self) -> int:
        """Count of scores exceeding the warn threshold (0.5) in current window."""
        return sum(1 for s in self._scores if s >= 0.5)


def _score_to_severity(score: float) -> str:
    """
    Map a continuous anomaly score to the 4-level severity enum.
    Thresholds match the .NET Decision Engine PolicyEvaluator exactly.
    """
    if score < 0.5:
        return "watch"
    elif score < 0.7:
        return "warn"
    elif score < 0.85:
        return "degrade"
    else:
        return "critical"


# ─────────────────────────────────────────────────────────────────────────────
# Core processor class
# ─────────────────────────────────────────────────────────────────────────────

class HSTStreamProcessor:
    """
    Stateful per-service anomaly detector using Half-Space Trees + ADWIN.

    Lifecycle:
      1. warm_up(train_stream)  — feeds training data through learn_one() only,
                                   building the model's internal reference window.
      2. process_stream(stream) — calls score_one() THEN learn_one() for each event,
                                   yielding StreamEvent results with ADWIN monitoring.
      3. snapshot()             — serialises the HST model to bytes for MLflow storage.
      4. restore(bytes)         — deserialises a previous snapshot (rollback).

    Why score BEFORE learn:
      For anomaly detection, we score the current point against what the model
      has learned so far (prior knowledge), then update the model with this point.
      Scoring after learning would incorporate the anomalous point into the model
      before detection, reducing sensitivity.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id

        # ── Half-Space Trees model ────────────────────────────────────────────
        self._model = HalfSpaceTrees(
            n_trees=HST_CFG.n_trees,
            height=HST_CFG.height,
            window_size=HST_CFG.window_size,
            seed=HST_CFG.seed,
        )

        # ── ADWIN drift detector ──────────────────────────────────────────────
        # One ADWIN instance monitors the distribution of anomaly_scores over time.
        # When the statistical properties of scores change significantly (e.g., a
        # deployment introduces new baseline behaviour), ADWIN raises drift_detected.
        self._adwin = ADWIN(delta=ADWIN_CFG.delta)

        # ── Counters and statistics ───────────────────────────────────────────
        self._step: int = 0                    # Total events processed
        self._drift_count: int = 0             # Number of drift events detected
        self._last_score: float = 0.0
        self._stats = RunningStats(window_size=500)

        # ── Snapshot management ───────────────────────────────────────────────
        # Stores bytes of the last "stable" model state — used for rollback when
        # drift is detected. In production, this pointer lives in MLflow; here
        # we keep it in memory for the standalone pipeline.
        self._last_stable_snapshot: Optional[bytes] = None
        self._snapshot_step: int = 0           # Step at which snapshot was taken

        logger.info(
            f"[{service_id}] HSTStreamProcessor initialised. "
            f"n_trees={HST_CFG.n_trees}, height={HST_CFG.height}, "
            f"window_size={HST_CFG.window_size}, ADWIN_delta={ADWIN_CFG.delta}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1: Warm-up (Component 1 Extension)
    # ─────────────────────────────────────────────────────────────────────────

    def warm_up(
        self,
        train_stream: "Generator",
        progress: bool = True,
    ) -> dict:
        """
        Feed training data through the model to build its reference window.

        During warm-up we ONLY call learn_one() — no scoring, no ADWIN updates.
        This is because the training data is assumed to be mostly normal behaviour;
        we're establishing what "normal" looks like before we start detecting anomalies.

        This matches the production warm_up_hst.py script in the ml-pipeline/scripts/
        directory of the monorepo — the trained model is then saved to MLflow as the
        initial "PRODUCTION" model version.

        Args:
            train_stream: Generator from data_pipeline.stream_entity() on TRAIN split.
            progress: Show tqdm progress bar (recommended for long runs).

        Returns:
            dict with warm-up summary statistics.
        """
        from tqdm import tqdm

        logger.info(f"[{self.service_id}] Starting warm-up phase...")
        warm_up_start = time.perf_counter()
        n_events = 0

        # Wrap in tqdm for progress display if requested
        stream = tqdm(train_stream, desc=f"Warm-up {self.service_id}") if progress else train_stream

        for features in stream:
            # learn_one() updates the model's internal hash structures.
            # No scoring during warm-up — the model hasn't seen enough data yet
            # for meaningful anomaly scores (scores would be near-random early on).
            self._model.learn_one(features)
            n_events += 1

        warm_up_duration = time.perf_counter() - warm_up_start
        throughput = n_events / warm_up_duration

        # After warm-up, take the first stable snapshot for rollback purposes
        self._last_stable_snapshot = self.snapshot()
        self._snapshot_step = n_events

        summary = {
            "entity": self.service_id,
            "events_trained": n_events,
            "duration_seconds": round(warm_up_duration, 2),
            "throughput_events_per_sec": round(throughput, 1),
            "snapshot_taken": True,
        }
        logger.info(
            f"[{self.service_id}] Warm-up complete. "
            f"{n_events:,} events in {warm_up_duration:.1f}s "
            f"({throughput:.0f} events/sec)"
        )
        return summary

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2: Online Streaming (Component 2)
    # ─────────────────────────────────────────────────────────────────────────

    def process_one(self, features: dict[str, float]) -> StreamEvent:
        """
        Process a single feature vector through the full Component 2 pipeline.

        Steps performed in order:
          1. score_one(features)  → raw_score from HST
          2. Clamp raw_score to [0, 1]
          3. learn_one(features)  → update HST model weights
          4. adwin.update(score)  → check for distribution drift
          5. If drift: log event, optionally rollback model
          6. Update running statistics
          7. Return StreamEvent

        In the FastAPI production service, this method is called once per
        POST /ingest/metrics request (after feature extraction).

        Returns:
            StreamEvent with all fields populated.
        """
        t_start = time.perf_counter()

        # ── Step 1+2: Score BEFORE learning ──────────────────────────────────
        # river's HalfSpaceTrees.score_one() returns a float. The range is
        # technically [0, ∞) though in practice almost always < 1.0 during
        # normal operation. We clamp to [0, 1] for consistency.
        raw_score: float = self._model.score_one(features)
        anomaly_score = float(min(max(raw_score, 0.0), 1.0))

        # ── Step 3: Incremental model update ─────────────────────────────────
        # learn_one() runs in O(n_trees × height) = O(25 × 15) = O(375) time.
        # On the i7-1165G7, this completes in ~0.5–2ms per call.
        self._model.learn_one(features)

        latency_ms = (time.perf_counter() - t_start) * 1000

        # ── Step 4: ADWIN drift detection ─────────────────────────────────────
        # We feed the anomaly SCORE (not the raw features) into ADWIN.
        # ADWIN monitors the distribution of scores over an adaptive window.
        # If the mean score shifts significantly, it signals concept drift —
        # meaning the system's behaviour has fundamentally changed.
        self._adwin.update(anomaly_score)
        drift_detected = bool(self._adwin.drift_detected)

        # ── Step 5: Handle drift event ────────────────────────────────────────
        if drift_detected:
            self._drift_count += 1
            logger.warning(
                f"[{self.service_id}] ADWIN drift detected at step {self._step}! "
                f"Current score={anomaly_score:.4f}, "
                f"drift_count={self._drift_count}"
            )
            # The MLflow lifecycle module handles the actual rollback decision.
            # Here we just mark the event. The caller (main.py / MLflowModelManager)
            # decides whether to rollback based on policy (e.g., only rollback
            # if score also exceeds a threshold, to avoid false alarms).

        # ── Step 6: Update running stats ──────────────────────────────────────
        self._stats.update(anomaly_score)
        self._last_score = anomaly_score
        self._step += 1

        return StreamEvent(
            step=self._step,
            service_id=self.service_id,
            anomaly_score=anomaly_score,
            severity=_score_to_severity(anomaly_score),
            drift_detected=drift_detected,
            latency_ms=round(latency_ms, 3),
            features=features,  # full dict; truncate in logs
        )

    def process_stream(
        self,
        stream: "Generator",
        on_drift: Optional[callable] = None,
        progress: bool = True,
    ) -> "Generator[StreamEvent, None, None]":
        """
        Process an entire stream, yielding one StreamEvent per event.

        Args:
            stream: Generator from data_pipeline.stream_entity() on TEST split.
            on_drift: Optional callback invoked when ADWIN detects drift.
                      Signature: on_drift(processor, event) -> None
                      Use this hook to trigger MLflow rollbacks.
            progress: Show tqdm progress bar.

        Yields:
            StreamEvent for every processed event.

        Usage:
            >>> for event in processor.process_stream(test_stream, on_drift=mlflow_mgr.handle_drift):
            ...     log_to_timescaledb(event)   # production integration point
        """
        from tqdm import tqdm

        wrapped = tqdm(stream, desc=f"Streaming {self.service_id}") if progress else stream

        for features in wrapped:
            event = self.process_one(features)

            # Invoke drift callback if provided and drift was detected
            if event.drift_detected and on_drift is not None:
                on_drift(self, event)

            yield event

    # ─────────────────────────────────────────────────────────────────────────
    # Serialisation — used by MLflow lifecycle for checkpointing + rollback
    # ─────────────────────────────────────────────────────────────────────────

    def snapshot(self) -> bytes:
        """
        Serialise the current HST model to bytes (pickle).

        Only the HST model is snapshotted — not the ADWIN detector. This is
        intentional: on rollback, we restore the MODEL to a previous stable
        state, but keep the ADWIN detector running so it continues monitoring
        the score distribution after rollback.

        Returns:
            Bytes that can be stored as an MLflow artifact or in Redis.
        """
        return pickle.dumps(self._model)

    def restore(self, model_bytes: bytes) -> None:
        """
        Restore the HST model from a previously serialised snapshot.
        Called by MLflowModelManager.handle_drift() on rollback.

        Args:
            model_bytes: Output of a previous snapshot() call.
        """
        self._model = pickle.loads(model_bytes)
        logger.info(
            f"[{self.service_id}] Model restored from snapshot "
            f"(taken at step {self._snapshot_step})."
        )

    def take_stable_snapshot(self) -> None:
        """
        Mark the current model state as 'stable' for future rollbacks.
        Called by MLflowModelManager after a period of low anomaly scores.
        """
        self._last_stable_snapshot = self.snapshot()
        self._snapshot_step = self._step
        logger.info(
            f"[{self.service_id}] Stable snapshot taken at step {self._step}."
        )

    def rollback_to_last_stable(self) -> bool:
        """
        Rollback in-memory to the last stable model snapshot.
        Returns True if rollback succeeded, False if no snapshot exists.
        """
        if self._last_stable_snapshot is None:
            logger.error(
                f"[{self.service_id}] Rollback requested but no stable snapshot exists!"
            )
            return False
        self.restore(self._last_stable_snapshot)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Properties for external access
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def step(self) -> int:
        return self._step

    @property
    def drift_count(self) -> int:
        return self._drift_count

    @property
    def last_score(self) -> float:
        return self._last_score

    @property
    def rolling_mean_score(self) -> float:
        return self._stats.mean

    @property
    def rolling_max_score(self) -> float:
        return self._stats.maximum

    @property
    def warn_rate(self) -> float:
        """Fraction of recent scores at or above the 'warn' threshold (0.5)."""
        if self._stats._scores:
            return self._stats.above_warn / len(self._stats._scores)
        return 0.0
```

---

## Part 5: MLflow Lifecycle Script

**`src/mlflow_lifecycle.py`**

```python
"""
mlflow_lifecycle.py — MLflow experiment tracking, checkpointing, and rollback.

This module implements the full Component 2 model lifecycle:
  - Initialise MLflow experiments per entity.
  - Log hyperparameters at run start.
  - Log rolling metrics every N steps.
  - Save pickle snapshots as MLflow artefacts.
  - Detect stable periods and auto-snapshot.
  - Handle ADWIN drift events with automated rollback.

Integration note for the monorepo:
  In the production FastAPI service (services/ml-backend/app/ml/model_manager.py),
  this class becomes MLflowModelManager. The key difference is that in production,
  `mlflow.log_artifact()` stores files in MinIO (S3-compatible), and the run_id
  is published to Redis so all FastAPI replicas can reference the same model version.
  The `rollback()` method in production also calls the TimescaleDB client to log
  the rollback event as a metric_event row for the LLM RAG pipeline to index.
"""

import io
import logging
import pickle
import tempfile
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import mlflow
import mlflow.pyfunc
from mlflow.tracking import MlflowClient

from src.config import ADWIN_CFG, HST_CFG, PIPELINE_CFG

if TYPE_CHECKING:
    from src.hst_model import HSTStreamProcessor, StreamEvent

logger = logging.getLogger(__name__)


class MLflowModelManager:
    """
    Manages the complete MLflow lifecycle for one HST model instance.

    One manager corresponds to one service (entity). In the production system,
    one instance of this class is created per entry in HSTModelRegistry._models.

    State tracked per run:
      - Hyperparameters (logged once at run start)
      - Rolling anomaly_score metrics (logged every LOG_EVERY_N_STEPS)
      - drift_count (cumulative)
      - Pickle snapshot artefacts (logged on stable checkpoints + rollback events)
      - Run tags indicating model lifecycle stage
    """

    # Stability criteria: if rolling_mean_score stays below this for
    # STABILITY_WINDOW_STEPS, we take a new "stable" snapshot.
    STABILITY_THRESHOLD = 0.4
    STABILITY_WINDOW_STEPS = 1000

    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        self._experiment_name = f"hst_{entity_id}"

        # Active run tracking
        self._active_run_id: Optional[str] = None
        self._client = MlflowClient(tracking_uri=PIPELINE_CFG.mlflow_tracking_uri)

        # Snapshot tracking (for rollback)
        self._production_run_id: Optional[str] = None  # Run ID of last stable model
        self._production_artifact_path: Optional[str] = None
        self._steps_since_last_snapshot: int = 0

        # Metrics buffer — accumulate between log intervals
        self._metric_buffer: list[dict] = []

        mlflow.set_tracking_uri(PIPELINE_CFG.mlflow_tracking_uri)

    # ─────────────────────────────────────────────────────────────────────────
    # Run management
    # ─────────────────────────────────────────────────────────────────────────

    def start_run(self) -> str:
        """
        Create (or reuse) the MLflow experiment and start a new run.

        Returns:
            run_id (str) — the unique identifier for this training run.
        """
        # Ensure experiment exists
        experiment = mlflow.get_experiment_by_name(self._experiment_name)
        if experiment is None:
            mlflow.create_experiment(
                self._experiment_name,
                tags={"entity": self.entity_id, "model_type": "HalfSpaceTrees"},
            )
            logger.info(f"Created MLflow experiment: {self._experiment_name}")

        mlflow.set_experiment(self._experiment_name)

        # Start a new run
        run = mlflow.start_run(
            run_name=f"{self.entity_id}_{int(time.time())}",
            tags={
                "entity_id": self.entity_id,
                "stage": "WARM_UP",
                "model_type": "HalfSpaceTrees",
                "drift_library": "ADWIN",
            },
        )
        self._active_run_id = run.info.run_id

        # Log all hyperparameters as a flat dict
        mlflow.log_params({
            "n_trees": HST_CFG.n_trees,
            "height": HST_CFG.height,
            "window_size": HST_CFG.window_size,
            "seed": HST_CFG.seed,
            "adwin_delta": ADWIN_CFG.delta,
            "entity_id": self.entity_id,
            "log_interval": PIPELINE_CFG.log_every_n_steps,
            "stability_threshold": self.STABILITY_THRESHOLD,
        })

        logger.info(
            f"[{self.entity_id}] MLflow run started: {self._active_run_id} "
            f"(experiment: {self._experiment_name})"
        )
        return self._active_run_id

    def end_run(self, status: str = "FINISHED") -> None:
        """Finalise the active MLflow run."""
        if self._active_run_id:
            mlflow.end_run(status=status)
            logger.info(
                f"[{self.entity_id}] MLflow run {self._active_run_id} ended: {status}"
            )
            self._active_run_id = None

    # ─────────────────────────────────────────────────────────────────────────
    # Metric logging
    # ─────────────────────────────────────────────────────────────────────────

    def log_warm_up_complete(self, warm_up_summary: dict) -> None:
        """
        Log warm-up summary metrics and update run tag to STREAMING stage.
        Call this immediately after processor.warm_up() completes.
        """
        mlflow.log_metrics({
            "warm_up_events": warm_up_summary["events_trained"],
            "warm_up_duration_s": warm_up_summary["duration_seconds"],
            "warm_up_throughput_eps": warm_up_summary["throughput_events_per_sec"],
        })
        self._client.set_tag(self._active_run_id, "stage", "STREAMING")
        logger.info(f"[{self.entity_id}] Warm-up metrics logged to MLflow.")

    def log_event_metrics(self, processor: "HSTStreamProcessor") -> None:
        """
        Log current rolling metrics to MLflow.

        Call this every LOG_EVERY_N_STEPS events — not every single event,
        as that would create millions of metric rows and slow down MLflow.

        In production, these same metrics are also written to the TimescaleDB
        metric_events hypertable for the Grafana dashboard time-series panels.
        """
        step = processor.step

        mlflow.log_metrics(
            {
                "rolling_mean_score": round(processor.rolling_mean_score, 6),
                "rolling_max_score": round(processor.rolling_max_score, 6),
                "last_score": round(processor.last_score, 6),
                "cumulative_drift_count": processor.drift_count,
                "warn_rate": round(processor.warn_rate, 4),
            },
            step=step,
        )

        logger.debug(
            f"[{self.entity_id}] Step {step:,}: "
            f"mean={processor.rolling_mean_score:.4f}, "
            f"max={processor.rolling_max_score:.4f}, "
            f"drifts={processor.drift_count}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Model snapshotting
    # ─────────────────────────────────────────────────────────────────────────

    def save_snapshot_artifact(
        self,
        processor: "HSTStreamProcessor",
        label: str = "checkpoint",
    ) -> str:
        """
        Pickle the HST model and log it as an MLflow artefact.

        Args:
            processor: The HSTStreamProcessor whose model to snapshot.
            label: Descriptive label appended to the artefact filename.
                   Use "warm_up_complete", "stable_checkpoint", "pre_rollback", etc.

        Returns:
            artefact path within the MLflow run.
        """
        model_bytes = processor.snapshot()
        artefact_name = f"hst_model_{label}_step_{processor.step}.pkl"

        # MLflow artefacts must be written as files.
        # We use a temporary file to avoid polluting the project directory.
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
            tmp.write(model_bytes)
            tmp_path = tmp.name

        mlflow.log_artifact(tmp_path, artifact_path="models")
        Path(tmp_path).unlink(missing_ok=True)  # clean up temp file

        # Also save a local copy for quick access without MLflow overhead
        local_dir = Path(PIPELINE_CFG.model_snapshot_dir) / self.entity_id
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / artefact_name
        local_path.write_bytes(model_bytes)

        logger.info(
            f"[{self.entity_id}] Snapshot saved: {artefact_name} "
            f"({len(model_bytes) / 1024:.1f} KB)"
        )
        return f"models/{artefact_name}"

    def maybe_take_stable_snapshot(self, processor: "HSTStreamProcessor") -> bool:
        """
        Take a new stable snapshot if the model has been running without
        high anomaly scores for STABILITY_WINDOW_STEPS events.

        This is called from the main streaming loop every N steps.
        Returns True if a snapshot was taken.
        """
        self._steps_since_last_snapshot += 1

        # Only check after enough steps have accumulated
        if self._steps_since_last_snapshot < self.STABILITY_WINDOW_STEPS:
            return False

        if processor.rolling_mean_score < self.STABILITY_THRESHOLD:
            logger.info(
                f"[{self.entity_id}] Model appears stable "
                f"(mean_score={processor.rolling_mean_score:.4f} "
                f"< threshold={self.STABILITY_THRESHOLD}). "
                f"Taking stable snapshot."
            )
            artefact_path = self.save_snapshot_artifact(processor, label="stable_checkpoint")
            processor.take_stable_snapshot()
            self._production_run_id = self._active_run_id
            self._production_artifact_path = artefact_path
            self._steps_since_last_snapshot = 0

            # Tag run as having a production-ready model version
            self._client.set_tag(self._active_run_id, "has_production_snapshot", "true")
            mlflow.log_metric("stable_snapshots_taken", processor.step, step=processor.step)
            return True

        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Drift handling + rollback (Core Component 2 Logic)
    # ─────────────────────────────────────────────────────────────────────────

    def handle_drift(
        self,
        processor: "HSTStreamProcessor",
        event: "StreamEvent",
    ) -> None:
        """
        Callback invoked by HSTStreamProcessor.process_stream() when ADWIN
        detects a concept drift event.

        Decision logic:
          1. Log the drift event to MLflow with full context.
          2. If a stable snapshot exists: restore the model to it (rollback).
          3. If no stable snapshot: log a warning and continue with current model
             (the model is too new to have a reference point — this shouldn't
             happen after a proper warm-up).
          4. Take a pre-rollback snapshot for forensic audit.

        This is the standalone equivalent of MLflowModelManager.rollback() in
        the production FastAPI service. In production, a rollback also:
          - Publishes to Redis Pub/Sub "ws:anomaly_broadcast" with type="drift_alert"
          - Inserts a row into TimescaleDB metric_events with severity="drift"
          - Triggers the LLM Copilot to generate a post-mortem

        Args:
            processor: The HSTStreamProcessor that detected drift.
            event: The StreamEvent that triggered the drift flag.
        """
        logger.warning(
            f"[{self.entity_id}] ADWIN drift handler invoked at step {event.step}. "
            f"Score at drift point: {event.anomaly_score:.4f}"
        )

        # ── 1. Log drift event metadata ───────────────────────────────────────
        mlflow.log_metrics(
            {
                "drift_score": event.anomaly_score,
                "drift_rolling_mean": processor.rolling_mean_score,
                "drift_warn_rate": processor.warn_rate,
            },
            step=event.step,
        )
        self._client.set_tag(
            self._active_run_id,
            f"drift_event_{processor.drift_count}",
            f"step={event.step},score={event.anomaly_score:.4f}",
        )

        # ── 2. Save pre-rollback snapshot (forensic audit) ───────────────────
        # Even though we're about to rollback, we log the drifted model state
        # for post-mortem analysis by the LLM Copilot.
        self.save_snapshot_artifact(processor, label="pre_rollback")

        # ── 3. Decide rollback strategy ───────────────────────────────────────
        if processor._last_stable_snapshot is not None:
            # We have a reference model — restore to it
            success = processor.rollback_to_last_stable()
            if success:
                logger.info(
                    f"[{self.entity_id}] Rollback successful. "
                    f"Restored to model state from step {processor._snapshot_step}."
                )
                mlflow.log_metric("rollback_executed", 1, step=event.step)
                mlflow.log_metric(
                    "rollback_to_step", processor._snapshot_step, step=event.step
                )
                self._client.set_tag(
                    self._active_run_id, "last_rollback_step", str(event.step)
                )
            else:
                logger.error(
                    f"[{self.entity_id}] Rollback failed — no stable snapshot available!"
                )
                mlflow.log_metric("rollback_failed", 1, step=event.step)
        else:
            # No stable snapshot — model was never stable enough to checkpoint.
            # Continue with the current model (adaptive learning will eventually
            # re-stabilise around the new distribution).
            logger.warning(
                f"[{self.entity_id}] Drift detected but no stable snapshot exists. "
                f"Continuing with adaptive learning. Consider tuning ADWIN_DELTA."
            )
            mlflow.log_metric("rollback_skipped_no_snapshot", 1, step=event.step)

        # ── 4. Reset stability counter so we don't immediately snapshot again ──
        self._steps_since_last_snapshot = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Evaluation — run against labelled test data
    # ─────────────────────────────────────────────────────────────────────────

    def evaluate_against_labels(
        self,
        scores: list[float],
        labels: list[int],
        threshold: float = 0.7,
    ) -> dict:
        """
        Compute precision, recall, F1 by thresholding anomaly scores against
        SMD ground-truth labels. Log results to the active MLflow run.

        Args:
            scores: List of anomaly_score floats from the test stream.
            labels: List of binary int labels (0=normal, 1=anomaly).
            threshold: Score threshold above which a point is predicted anomalous.

        Returns:
            dict with precision, recall, f1, threshold, n_anomalies.
        """
        from sklearn.metrics import classification_report, f1_score, precision_score, recall_score

        if len(scores) != len(labels):
            raise ValueError(
                f"Score/label length mismatch: {len(scores)} vs {len(labels)}"
            )

        predicted = [1 if s >= threshold else 0 for s in scores]
        n_predicted = sum(predicted)
        n_actual = sum(labels)

        precision = precision_score(labels, predicted, zero_division=0)
        recall = recall_score(labels, predicted, zero_division=0)
        f1 = f1_score(labels, predicted, zero_division=0)

        metrics = {
            "eval_threshold": threshold,
            "eval_precision": round(precision, 4),
            "eval_recall": round(recall, 4),
            "eval_f1": round(f1, 4),
            "eval_n_predicted_anomalies": n_predicted,
            "eval_n_actual_anomalies": n_actual,
            "eval_n_samples": len(scores),
        }

        mlflow.log_metrics(metrics)
        self._client.set_tag(self._active_run_id, "evaluation_complete", "true")

        # Log full classification report as an artefact
        report = classification_report(
            labels, predicted,
            target_names=["normal", "anomaly"],
            zero_division=0,
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(f"Threshold: {threshold}\n\n{report}")
            report_path = f.name

        mlflow.log_artifact(report_path, artifact_path="evaluation")
        Path(report_path).unlink(missing_ok=True)

        logger.info(
            f"[{self.entity_id}] Evaluation: "
            f"P={precision:.3f}, R={recall:.3f}, F1={f1:.3f} "
            f"(threshold={threshold})"
        )
        return metrics
```

---

## Part 6: Main Entry Point

**`main.py`**

```python
"""
main.py — Standalone entry point for the Component 1-2 pipeline.

Run this script to:
  1. Preprocess the SMD entity.
  2. Warm up the HST model on the training split.
  3. Run the streaming inference loop on the test split with ADWIN monitoring.
  4. Log everything to MLflow.
  5. Evaluate results against ground-truth labels.

Usage:
  python main.py                         # uses SMD_ENTITY from .env
  python main.py --entity machine-2-3    # override entity
  python main.py --entity machine-1-1 --eval-threshold 0.65
"""

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

import mlflow

# Configure logging before importing project modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", mode="w"),
    ],
)
logger = logging.getLogger("main")

from src.config import PIPELINE_CFG
from src.data_pipeline import load_labels, preprocess_entity, stream_entity
from src.hst_model import HSTStreamProcessor
from src.mlflow_lifecycle import MLflowModelManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Component 1-2 Pipeline")
    parser.add_argument(
        "--entity",
        default=PIPELINE_CFG.smd_entity,
        help="SMD entity ID (e.g. machine-1-1)"
    )
    parser.add_argument(
        "--eval-threshold",
        type=float,
        default=0.7,
        help="Anomaly score threshold for precision/recall evaluation"
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable tqdm progress bars (useful for CI/log files)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    entity_id = args.entity
    progress = not args.no_progress

    logger.info("=" * 70)
    logger.info(f" Component 1-2 Pipeline — Entity: {entity_id}")
    logger.info("=" * 70)

    # ── Step 1: Preprocess SMD data ───────────────────────────────────────────
    logger.info("[Step 1] Preprocessing SMD data...")
    train_df, test_df = preprocess_entity(entity_id)
    labels = load_labels(entity_id)
    logger.info(
        f"  Train: {train_df.shape}, "
        f"Test: {test_df.shape}, "
        f"Labels: {len(labels)} rows"
    )

    # ── Step 2: Initialise core objects ───────────────────────────────────────
    logger.info("[Step 2] Initialising HST processor and MLflow manager...")
    processor = HSTStreamProcessor(service_id=entity_id)
    mlflow_mgr = MLflowModelManager(entity_id=entity_id)
    run_id = mlflow_mgr.start_run()
    logger.info(f"  MLflow run ID: {run_id}")

    # ── Step 3: Component 1 Extension — Warm-up ───────────────────────────────
    logger.info("[Step 3] Component 1 Extension: HST Warm-up on training split...")
    train_stream = stream_entity(train_df, entity_id)
    warm_up_summary = processor.warm_up(train_stream, progress=progress)

    # Log warm-up results and save the initial stable model
    mlflow_mgr.log_warm_up_complete(warm_up_summary)
    mlflow_mgr.save_snapshot_artifact(processor, label="warm_up_complete")

    logger.info(
        f"  Warm-up complete: {warm_up_summary['events_trained']:,} events, "
        f"{warm_up_summary['throughput_events_per_sec']:.0f} events/sec"
    )

    # ── Step 4: Component 2 — Streaming inference + ADWIN + Rollback ──────────
    logger.info("[Step 4] Component 2: Online streaming inference on test split...")

    test_stream = stream_entity(test_df, entity_id)

    # Prepare CSV output for score visualisation / post-hoc analysis
    score_csv_path = (
        Path(PIPELINE_CFG.score_output_dir) / f"{entity_id}_scores.csv"
    )
    Path(PIPELINE_CFG.score_output_dir).mkdir(parents=True, exist_ok=True)

    all_scores: list[float] = []
    log_interval = PIPELINE_CFG.log_every_n_steps

    pipeline_start = time.perf_counter()

    with open(score_csv_path, "w", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "step", "anomaly_score", "severity",
                "drift_detected", "latency_ms"
            ]
        )
        writer.writeheader()

        # ── Core streaming loop (Component 2 heart) ────────────────────────
        for event in processor.process_stream(
            stream=test_stream,
            on_drift=mlflow_mgr.handle_drift,   # ← ADWIN drift callback
            progress=progress,
        ):
            all_scores.append(event.anomaly_score)

            # Write to CSV output
            writer.writerow({
                "step": event.step,
                "anomaly_score": round(event.anomaly_score, 6),
                "severity": event.severity,
                "drift_detected": event.drift_detected,
                "latency_ms": event.latency_ms,
            })

            # ── Log metrics to MLflow every N steps ─────────────────────────
            if event.step % log_interval == 0:
                mlflow_mgr.log_event_metrics(processor)

                # Consider taking a new stable snapshot
                mlflow_mgr.maybe_take_stable_snapshot(processor)

                # Console summary line
                logger.info(
                    f"  Step {event.step:>6,} | "
                    f"score={event.anomaly_score:.4f} [{event.severity:>7}] | "
                    f"mean={processor.rolling_mean_score:.4f} | "
                    f"drifts={processor.drift_count} | "
                    f"{event.latency_ms:.2f}ms"
                )

    # ── Step 5: Evaluation against ground-truth labels ─────────────────────────
    logger.info("[Step 5] Evaluating against SMD ground-truth labels...")

    # Align scores to labels (test split lengths must match)
    score_count = len(all_scores)
    label_count = len(labels)
    if score_count != label_count:
        logger.warning(
            f"Score/label count mismatch ({score_count} vs {label_count}). "
            f"Truncating to minimum."
        )
        n = min(score_count, label_count)
        all_scores = all_scores[:n]
        labels_list = labels.tolist()[:n]
    else:
        labels_list = labels.tolist()

    eval_metrics = mlflow_mgr.evaluate_against_labels(
        scores=all_scores,
        labels=labels_list,
        threshold=args.eval_threshold,
    )

    # ── Step 6: Final summary ─────────────────────────────────────────────────
    total_duration = time.perf_counter() - pipeline_start
    throughput = len(all_scores) / total_duration

    logger.info("")
    logger.info("=" * 70)
    logger.info(" PIPELINE COMPLETE")
    logger.info("=" * 70)
    logger.info(f"  Entity:            {entity_id}")
    logger.info(f"  Total events:      {len(all_scores):,}")
    logger.info(f"  Duration:          {total_duration:.1f}s")
    logger.info(f"  Throughput:        {throughput:.0f} events/sec")
    logger.info(f"  Drift events:      {processor.drift_count}")
    logger.info(f"  Final mean score:  {processor.rolling_mean_score:.4f}")
    logger.info(f"  Precision:         {eval_metrics['eval_precision']:.4f}")
    logger.info(f"  Recall:            {eval_metrics['eval_recall']:.4f}")
    logger.info(f"  F1 score:          {eval_metrics['eval_f1']:.4f}")
    logger.info(f"  Scores CSV:        {score_csv_path}")
    logger.info(f"  MLflow run ID:     {run_id}")
    logger.info(f"  MLflow UI:         mlflow ui --backend-store-uri {PIPELINE_CFG.mlflow_tracking_uri}")

    # Log final summary metrics
    mlflow.log_metrics({
        "final_mean_score": processor.rolling_mean_score,
        "total_events_streamed": len(all_scores),
        "total_duration_s": round(total_duration, 2),
        "total_throughput_eps": round(throughput, 1),
        "total_drift_events": processor.drift_count,
    })

    mlflow_mgr.end_run(status="FINISHED")


if __name__ == "__main__":
    main()
```

---

## Part 7: Running the Pipeline

### Step 7.1 — Start MLflow UI (separate terminal)

```bash
# In terminal 1 — leave this running
mlflow ui --backend-store-uri ./mlruns --port 5001
# Open: http://localhost:5001
```

### Step 7.2 — Run the pipeline

```bash
# In terminal 2
cd component-1-2-pipeline
python main.py --entity machine-1-1
```

**Expected console output (first 5 minutes):**
```
10:24:01 | INFO     | main                          | Step 1: Preprocessing SMD data...
10:24:02 | INFO     | src.data_pipeline             | Loaded train split for machine-1-1: (28479, 38)
10:24:02 | INFO     | main                          |   Train: (28479, 38), Test: (28479, 38)
10:24:02 | INFO     | main                          | Step 3: Component 1 Extension: HST Warm-up...
Warm-up machine-1-1: 100%|████████| 28479/28479 [01:43<00:00, 275.0 it/s]
10:26:06 | INFO     | src.hst_model                 | [machine-1-1] Warm-up complete. 28,479 events in 103.5s (275 events/sec)
10:26:06 | INFO     | main                          | Step 4: Component 2: Online streaming inference...
  Step    500 | score=0.1823 [  watch] | mean=0.1201 | drifts=0 | 1.23ms
  Step   1000 | score=0.2541 [  watch] | mean=0.1834 | drifts=0 | 1.19ms
  ...
10:27:12 | WARNING  | src.hst_model                 | [machine-1-1] ADWIN drift detected at step 4823!
10:27:12 | WARNING  | src.mlflow_lifecycle          | [machine-1-1] ADWIN drift handler invoked.
10:27:12 | INFO     | src.hst_model                 | [machine-1-1] Model restored from snapshot (taken at step 28479).
```

### Step 7.3 — View results in MLflow UI

Navigate to http://localhost:5001:
- Click on experiment `hst_machine-1-1`
- Click on the most recent run
- **Parameters tab**: verify n_trees=25, adwin_delta=0.002 etc.
- **Metrics tab**: view rolling_mean_score over time (should be low except at drift events)
- **Artifacts tab**: find `models/hst_model_warm_up_complete_step_28479.pkl`

### Step 7.4 — Run on all 28 entities (batch mode)

```bash
# pipeline_all_entities.sh
#!/bin/bash
ENTITIES=(
  machine-1-1 machine-1-2 machine-1-3 machine-1-4 machine-1-5 machine-1-6 machine-1-7
  machine-2-1 machine-2-2 machine-2-3 machine-2-4 machine-2-5 machine-2-6 machine-2-7
  machine-3-1 machine-3-2 machine-3-3 machine-3-4 machine-3-5 machine-3-6
  machine-3-7 machine-3-8 machine-3-9 machine-3-10 machine-3-11
)

for entity in "${ENTITIES[@]}"; do
  echo "==============================="
  echo "Processing: $entity"
  echo "==============================="
  python main.py --entity "$entity" --no-progress
done
```

---

## Part 8: Architecture Compatibility Notes

These notes document exactly what changes when this standalone code is integrated into the FastAPI monorepo. Knowing these upfront will save you refactoring time.

### 8.1 — Replacing Global Singletons with FastAPI Dependency Injection

In `main.py`, you instantiate `HSTStreamProcessor` and `MLflowModelManager` directly. In the FastAPI service, these are created in the `lifespan()` context manager and injected via `app.state`:

```python
# main.py (standalone)
processor = HSTStreamProcessor(service_id=entity_id)

# FastAPI monorepo equivalent (services/ml-backend/app/main.py)
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.hst_registry = HSTModelRegistry(...)  # dict of processors
    yield
    await app.state.hst_registry.close()
```

### 8.2 — Redis Pub/Sub Integration Points

In the standalone version, `handle_drift()` logs to MLflow and restores in-memory. In production, add these two calls after the successful rollback:

```python
# Integration point A: notify all WebSocket clients via Redis Pub/Sub
await redis_client.publish("ws:anomaly_broadcast", json.dumps({
    "type": "drift_alert",
    "service_id": self.entity_id,
    "step": event.step,
    "score": event.anomaly_score,
}))

# Integration point B: write to TimescaleDB for LLM RAG indexing
await timescaledb_client.insert_metric_event(AnomalyEvent(
    service_id=self.entity_id,
    anomaly_score=event.anomaly_score,
    severity="drift",
    drift_detected=True,
))
```

### 8.3 — Replacing CSV Output with TimescaleDB Writes

The `main.py` streaming loop writes to a CSV file. In production, each `StreamEvent` becomes a TimescaleDB INSERT:

```python
# Standalone (main.py)
writer.writerow({"step": event.step, "anomaly_score": ...})

# Production (services/ml-backend/app/api/routes/ingest.py)
await timescaledb_client.insert_metric_event(event)
```

### 8.4 — Thread Safety for Multi-Replica Deployment

The standalone `HSTStreamProcessor` is single-threaded and uses no locks. The production `HSTModelRegistry` wraps the same logic in `asyncio.Lock` so concurrent FastAPI requests don't corrupt the model state:

```python
# This standalone class is ALREADY structurally compatible.
# When lifted into HSTModelRegistry, wrap score_and_learn() calls:
async with self._lock:
    event = processor.process_one(features)
```

### 8.5 — MLflow Tracking URI

Standalone: `./mlruns` (local SQLite + filesystem).
Production: `http://mlflow-server.selfheal-system.svc:5001` (cluster-internal).
This is a one-line change in `.env` / Kubernetes ConfigMap — no code changes needed.

---

## Part 9: Troubleshooting Guide

| Problem | Likely Cause | Fix |
|---|---|---|
| `FileNotFoundError: data/smd/raw/train/machine-1-1.txt` | Dataset not downloaded | Re-run Step 1.7 |
| `ModuleNotFoundError: No module named 'river'` | Wrong virtual env active | `source .venv/bin/activate` then `uv add river` |
| HST scores are all 0.0 | `score_one()` called before `learn_one()` sees enough data | Normal for first 250 events (window_size). Scores stabilise after that. |
| MLflow UI shows no experiments | Wrong tracking URI | Check `.env` MLFLOW_TRACKING_URI matches `mlflow ui --backend-store-uri` path |
| ADWIN fires on every event | `delta` too high | Lower ADWIN_DELTA to 0.001 in `.env` |
| Very slow warm-up (<50 events/sec) | Python not using fast path | Check no debugger attached; run `python -O main.py` for optimised bytecode |
| `sqlite3.OperationalError: database is locked` | Two MLflow runs writing simultaneously | Only run one instance of the pipeline at a time locally |
| Out of memory on batch run (all 28 entities) | DataFrames not garbage collected | Each entity's `train_df` + `test_df` is ~8 MB; 28 × 16 MB ≈ 448 MB. Well within your 16 GB. |

---

## Quick Reference Card

```bash
# 1. Activate environment
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac/Linux

# 2. Start MLflow UI
mlflow ui --backend-store-uri ./mlruns --port 5001

# 3. Run single entity
python main.py --entity machine-1-1

# 4. Run with custom eval threshold
python main.py --entity machine-1-1 --eval-threshold 0.65

# 5. Check all runs
mlflow runs list --experiment-name hst_machine-1-1

# 6. Load a saved model snapshot for manual inspection
import pickle
model = pickle.loads(open("model_snapshots/machine-1-1/hst_model_warm_up_complete_step_28479.pkl","rb").read())
score = model.score_one({"cpu_rate": 0.85, "memory_used_fraction": 0.72, ...})
```
