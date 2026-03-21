"""Unit tests for src.config — Pydantic settings loader."""

import os

import pytest

from src.config import Settings, get_settings


class TestSettings:
    """Test the Settings class loads and validates configuration."""

    def test_settings_loads_defaults(self, monkeypatch):
        """Settings should provide sensible defaults when env vars are missing."""
        for key in [
            "HOST", "PORT", "ENV", "API_KEYS", "DATABASE_URL",
            "SLOT_INCREMENT_MINUTES", "DEFAULT_BUFFER_MINUTES",
            "MAX_DAILY_APPOINTMENTS", "OVERBOOK_DEFAULT", "LOG_LEVEL",
        ]:
            monkeypatch.delenv(key, raising=False)

        settings = Settings(_env_file=None)
        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 8000
        assert settings.ENV == "development"
        assert settings.LOG_LEVEL == "info"
        assert settings.SLOT_INCREMENT_MINUTES == 15
        assert settings.DEFAULT_BUFFER_MINUTES == 10
        assert settings.MAX_DAILY_APPOINTMENTS == 20
        assert settings.OVERBOOK_DEFAULT == 0

    def test_settings_loads_from_env(self, monkeypatch):
        """Settings should read values from environment variables."""
        monkeypatch.setenv("HOST", "127.0.0.1")
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("API_KEYS", "key-a,key-b,key-c")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@host:5432/db")
        monkeypatch.setenv("LOG_LEVEL", "debug")

        settings = Settings(_env_file=None)
        assert settings.HOST == "127.0.0.1"
        assert settings.PORT == 9000
        assert settings.ENV == "production"
        assert settings.api_keys_list == ["key-a", "key-b", "key-c"]
        assert settings.LOG_LEVEL == "debug"

    def test_api_keys_parsed_as_list(self, monkeypatch):
        """API_KEYS env var should be split into a list on commas."""
        monkeypatch.setenv("API_KEYS", "alpha,bravo,charlie")

        settings = Settings(_env_file=None)
        assert isinstance(settings.api_keys_list, list)
        assert len(settings.api_keys_list) == 3
        assert "bravo" in settings.api_keys_list

    def test_get_settings_returns_cached_instance(self):
        """get_settings() should return the same instance on repeated calls."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
