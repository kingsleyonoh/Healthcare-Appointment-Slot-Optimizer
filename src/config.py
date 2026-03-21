"""Application configuration via Pydantic Settings.

Reads environment variables (or .env file) and provides a typed,
validated settings object. Use ``get_settings()`` for a cached singleton.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Typed application configuration."""

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENV: str = "development"
    API_KEYS: str = ""

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:devpass@localhost:5434/scheduler"

    # --- Scheduling ---
    SLOT_INCREMENT_MINUTES: int = 15
    DEFAULT_BUFFER_MINUTES: int = 10
    MAX_DAILY_APPOINTMENTS: int = 20
    OVERBOOK_DEFAULT: int = 0

    # --- Logging ---
    LOG_LEVEL: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def api_keys_list(self) -> list[str]:
        """Split comma-separated API_KEYS string into a list."""
        if not self.API_KEYS:
            return []
        return [k.strip() for k in self.API_KEYS.split(",") if k.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()
