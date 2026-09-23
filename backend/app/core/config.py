from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "dev-secret-change-me"
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Science Bank"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://science_bank:science_bank@postgres:5432/science_bank"
    standards_dir: Path = REPO_ROOT / "data" / "standards"
    static_dir: Path | None = None

    teacher_username: str = "nina"
    # Optional bootstrap: creates the teacher account on first start if no account exists yet.
    # Prefer `python -m app.cli set-password` which stores the hash in the database.
    teacher_password_hash: str = ""

    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    cors_origins: list[str] = []

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _refuse_insecure_production(self) -> "Settings":
        if self.is_production:
            if self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a random string of at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
