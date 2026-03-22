"""FastAPI application factory.

``create_app()`` builds and returns the fully configured FastAPI
instance with middleware, error handlers, and routes registered.

Lifespan handles APScheduler start/stop and database engine disposal.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.config_routes import router as config_router
from src.api.health import router as health_router
from src.db.session import get_engine
from src.lib.errors import register_error_handlers
from src.lib.logger import configure_logging
from src.lib.scheduler import create_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Manage startup and shutdown resources."""
    # --- Startup ---
    scheduler = create_scheduler()
    app.state.scheduler = scheduler
    scheduler.start()
    logger.info("APScheduler started")

    yield

    # --- Shutdown ---
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")

    engine = get_engine()
    await engine.dispose()
    logger.info("Database engine disposed")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    from src.config import get_settings

    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title="Healthcare Appointment Slot Optimizer",
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/docs" if settings.ENV != "production" else None,
        redoc_url=None,
    )

    # --- Error handlers ---
    register_error_handlers(app)

    # --- Routers ---
    app.include_router(health_router)
    app.include_router(config_router)

    return app


# Uvicorn entry point
app = create_app()
