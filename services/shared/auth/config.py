"""Auth configuration. Reads from the shared .env at services/shared/.env."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — reuse the Neon DB from decision-engine
    auth_db_url: str

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24h

    # Password reset
    reset_token_ttl_minutes: int = 60

    # Frontend base URL for reset links
    frontend_url: str = "http://localhost:5173"


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()