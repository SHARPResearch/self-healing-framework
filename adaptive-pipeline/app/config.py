"""Runtime settings for Component 3 — Adaptive Learning Decision Engine.
Reads ANOMALY_DB_URL from .env via pydantic-settings (same pattern as decision-engine).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    anomaly_db_url: str = ""          # never hard-code; comes from .env
    dqn_learning_rate: float = 0.001
    dqn_gamma: float = 0.95
    arbitration_mode: str = "hybrid"  # rule_only | hybrid | rl_preferred | rule_preferred

settings = Settings()