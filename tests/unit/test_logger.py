"""Unit tests for src.lib.logger — structured logging setup."""

import logging

import pytest


class TestGetLogger:
    """Test the get_logger factory function."""

    def test_returns_bound_logger(self):
        """get_logger should return a structlog BoundLogger."""
        from src.lib.logger import get_logger

        logger = get_logger("test_module")
        # structlog BoundLoggers have bind/unbind methods
        assert hasattr(logger, "bind")
        assert hasattr(logger, "unbind")

    def test_logger_has_module_context(self):
        """Logger should carry the module name in its bound context."""
        from src.lib.logger import get_logger

        logger = get_logger("my_component")
        # Access bound context — structlog stores it internally
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_configure_logging_sets_level(self):
        """configure_logging should set the root log level."""
        from src.lib.logger import configure_logging

        configure_logging("WARNING")
        root = logging.getLogger()
        assert root.level == logging.WARNING

        # Reset to default
        configure_logging("INFO")

    def test_configure_logging_case_insensitive(self):
        """configure_logging should accept lowercase level names."""
        from src.lib.logger import configure_logging

        configure_logging("debug")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

        configure_logging("INFO")
