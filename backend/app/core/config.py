from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Science Bank"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://science_bank:science_bank@postgres:5432/science_bank"

    # Single-teacher MVP auth (see PROJECT_STATUS.md section 4.4 — Phase 1).
    teacher_username: str = "nina"
    teacher_password_hash: str = ""  # bcrypt hash; set via env in production

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # one week

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
