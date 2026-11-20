"""Settings, read from environment variables."""

from datetime import datetime
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://l10:l10@localhost:5433/l10"

    # The seed's "now". The app never reads the system clock directly.
    app_now: datetime = datetime.fromisoformat("2026-11-11T15:00:00+00:00")
    # frozen: now() is always APP_NOW (tests, rules report).
    # running: now() starts at APP_NOW and advances in real time (the app).
    clock_mode: Literal["frozen", "running"] = "running"

    session_secret: str = "dev-only-change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
