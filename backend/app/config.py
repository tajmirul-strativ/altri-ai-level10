"""Settings, read from environment variables."""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
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
    cookie_secure: bool = False  # set true behind HTTPS

    # docs/seed.json at the repo root (mounted at /docs in Docker).
    seed_path: Path = Path(__file__).resolve().parents[2] / "docs" / "seed.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
