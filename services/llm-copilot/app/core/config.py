# Settings (DB URLs, LLM API keys, Component 2 URL)

"""
Centralized configuration management using pydantic-settings.
Loads from .env file and provides typed access to all settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM Settings 
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"

    # Component 2 Integration 
    component2_base_url: str = "http://localhost:8002"
    component2_webhook_secret: str = "change_this_secret"

    # Database 
    postgres_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/copilot_db"
    vector_db_path: str = "./data/chroma_db"

    # Security 
    masking_enabled: bool = True
    pii_detector_confidence_threshold: float = 0.85

    # Server 
    api_host: str = "0.0.0.0"
    api_port: int = 8004
    debug: bool = True


settings = Settings()