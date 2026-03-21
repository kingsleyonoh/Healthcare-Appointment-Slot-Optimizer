"""FastAPI application factory.

``create_app()`` builds and returns the fully configured FastAPI
instance with middleware, error handlers, and routes registered.
"""

from __future__ import annotations

from fastapi import FastAPI

from src.lib.errors import register_error_handlers
from src.lib.logger import configure_logging


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    from src.config import get_settings

    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title="Healthcare Appointment Slot Optimizer",
        version="0.1.0",
        docs_url="/docs" if settings.ENV != "production" else None,
        redoc_url=None,
    )

    # --- Error handlers ---
    register_error_handlers(app)

    # --- Health route (no auth) ---
    @app.get("/api/health", tags=["system"])
    async def health():
        return {"status": "healthy", "version": app.version}

    return app


# Uvicorn entry point
app = create_app()
