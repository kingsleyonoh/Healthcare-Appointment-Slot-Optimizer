"""Public health-check endpoint.

Returns application status, version, and database connectivity.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text

from src.db.session import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check() -> dict:
    """Return application health including database connectivity.

    Always returns HTTP 200 — the body indicates degraded state.
    """
    db_status = "disconnected"
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        logger.warning("Health check: database unreachable", exc_info=True)

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": "0.1.0",
        "database": db_status,
    }
