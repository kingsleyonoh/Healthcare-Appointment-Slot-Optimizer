"""FastAPI application factory.

``create_app()`` builds and returns the fully configured FastAPI
instance with middleware, error handlers, and routes registered.

Lifespan handles APScheduler start/stop and database engine disposal.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.booking_routes import router as booking_router
from src.api.config_routes import router as config_router
from src.api.health import router as health_router
from src.api.schedule import router as schedule_router
from src.api.slots import router as slots_router
from src.db.session import get_engine, get_session_factory
from src.integrations.notification_hub import NotificationHubClient
from src.jobs.no_show_marker import mark_no_shows
from src.lib.errors import register_error_handlers
from src.lib.logger import configure_logging
from src.lib.scheduler import create_scheduler

logger = logging.getLogger(__name__)


def _run_no_show_marker(hub: NotificationHubClient) -> None:
    """Sync wrapper to run the async no-show marker from APScheduler."""
    async def _inner():
        session_factory = get_session_factory()
        async with session_factory() as session:
            async with session.begin():
                count = await mark_no_shows(session=session, hub=hub)
                logger.info("Scheduled no-show marker: marked %d", count)

    asyncio.run(_inner())


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Manage startup and shutdown resources."""
    from src.config import get_settings

    settings = get_settings()

    # --- Startup ---
    hub = NotificationHubClient(
        url=settings.NOTIFICATION_HUB_URL,
        api_key=settings.NOTIFICATION_HUB_API_KEY,
        enabled=settings.NOTIFICATION_HUB_ENABLED,
    )
    app.state.notification_hub = hub

    scheduler = create_scheduler()
    app.state.scheduler = scheduler

    # Register background jobs
    scheduler.add_job(
        _run_no_show_marker,
        "interval",
        hours=1,
        args=[hub],
        id="no_show_marker",
        name="No-Show Marker",
    )

    scheduler.start()
    logger.info("APScheduler started with no-show marker job (every 1h)")

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
    app.include_router(slots_router)
    app.include_router(booking_router)
    app.include_router(schedule_router)

    return app


# Uvicorn entry point
app = create_app()
