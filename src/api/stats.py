"""Stats API route — GET /api/stats.

Returns daily statistics: utilization, booking count, no-show count.
Protected by API-key auth. Rate limit: 60/min.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import create_api_key_dependency
from src.config import get_settings
from src.db.session import get_session
from src.jobs.stats_calculator import calculate_stats

logger = logging.getLogger(__name__)

settings = get_settings()
router = APIRouter(prefix="/api", tags=["stats"])
_auth = create_api_key_dependency(settings.api_keys_list)


class StatsResponse(BaseModel):
    """Response schema for GET /api/stats."""

    utilization_today: float
    bookings_today: int
    no_shows: int


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> StatsResponse:
    """Return current daily statistics."""
    snapshot = await calculate_stats(session=session)
    return StatsResponse(
        utilization_today=snapshot.utilization_today,
        bookings_today=snapshot.bookings_today,
        no_shows=snapshot.no_shows,
    )
