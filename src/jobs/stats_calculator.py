"""Stats Calculator background job.

Computes daily stats (utilization, booking count, no-show count) from
the database. Results are returned as a ``StatsSnapshot`` and can be
cached in-memory by the caller for the stats API endpoint.

Runs on a schedule via APScheduler (configured in ``src/main.py``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import Booking, Provider, ProviderAvailability
from src.lib.time_utils import time_to_minutes
from src.optimizer.constraints import get_availability_windows

logger = logging.getLogger(__name__)


@dataclass
class StatsSnapshot:
    """Current stats snapshot for GET /api/stats."""

    utilization_today: float
    bookings_today: int
    no_shows: int


def _count_available_slots(
    windows: list[tuple[time, time]],
    slot_minutes: int,
) -> int:
    """Count how many slots of *slot_minutes* fit in availability windows."""
    total = 0
    for start, end in windows:
        available = time_to_minutes(end) - time_to_minutes(start)
        total += max(available // slot_minutes, 0)
    return total


async def calculate_stats(*, session: AsyncSession) -> StatsSnapshot:
    """Calculate current stats snapshot.

    - **utilization_today**: slots_used / slots_available across all providers
    - **bookings_today**: count of non-cancelled bookings on today's date
    - **no_shows**: count of no_show bookings on today's date
    """
    today = date.today()
    settings = get_settings()
    slot_minutes = settings.SLOT_INCREMENT_MINUTES

    # --- bookings_today: non-cancelled bookings ---
    bookings_today = (
        await session.execute(
            select(func.count(Booking.id)).where(
                Booking.date == today,
                Booking.status != "cancelled",
            )
        )
    ).scalar_one()

    # --- no_shows: no_show bookings ---
    no_shows = (
        await session.execute(
            select(func.count(Booking.id)).where(
                Booking.date == today,
                Booking.status == "no_show",
            )
        )
    ).scalar_one()

    # --- utilization_today: slots_used / slots_available ---
    providers = (
        await session.execute(
            select(Provider).where(Provider.enabled.is_(True))
        )
    ).scalars().all()

    if not providers:
        return StatsSnapshot(
            utilization_today=0.0,
            bookings_today=bookings_today,
            no_shows=no_shows,
        )

    provider_ids = [p.id for p in providers]

    # Load availability for all providers
    avail_rows = (
        await session.execute(
            select(ProviderAvailability).where(
                ProviderAvailability.provider_id.in_(provider_ids)
            )
        )
    ).scalars().all()

    # Count total available slots across all providers
    total_available = 0
    for provider in providers:
        p_avail = [a for a in avail_rows if a.provider_id == provider.id]
        windows = get_availability_windows(p_avail, today)
        total_available += _count_available_slots(windows, slot_minutes)

    if total_available == 0:
        return StatsSnapshot(
            utilization_today=0.0,
            bookings_today=bookings_today,
            no_shows=no_shows,
        )

    # Count non-cancelled bookings today as "slots used"
    utilization = min(bookings_today / total_available, 1.0)

    logger.debug(
        "Stats calculated: utilization=%.4f, bookings=%d, no_shows=%d, "
        "total_slots=%d, providers=%d",
        utilization, bookings_today, no_shows, total_available, len(providers),
    )

    return StatsSnapshot(
        utilization_today=round(utilization, 4),
        bookings_today=bookings_today,
        no_shows=no_shows,
    )
