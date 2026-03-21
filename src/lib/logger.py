"""Structured logging setup using structlog.

Provides ``get_logger()`` for module-scoped loggers and
``configure_logging()`` to set the root level at startup.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure stdlib + structlog at the given level.

    Args:
        level: Log level name (case-insensitive), e.g. ``"debug"``.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog BoundLogger scoped to *name*.

    Args:
        name: Logical module name, e.g. ``"optimizer.engine"``.
    """
    return structlog.get_logger(name)
