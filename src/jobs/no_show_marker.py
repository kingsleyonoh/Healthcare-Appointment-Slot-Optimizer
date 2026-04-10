"""No-Show Marker background job.

Finds confirmed bookings whose appointment end time has passed and
marks them as ``no_show``. Optionally emits ``appointment.no_show``
events to the Notification Hub.

Runs on a schedule via APScheduler (configured in ``src/main.py``).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Booking
from src.integrations.notification_hub import NotificationHubClient

logger = logging.getLogger(__name__)


async def mark_no_shows(
    *,
    session: AsyncSession,
    hub: NotificationHubClient | None = None,
) -> int:
    """Mark overdue confirmed bookings as no_show.

    A booking is overdue when ``date + end_time < now(UTC)``.

    Returns the number of bookings marked.
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    current_time = now.time()

    # Find confirmed bookings that have ended:
    #   - bookings on past dates are always overdue
    #   - bookings today are overdue if end_time < current time
    stmt = (
        select(Booking)
        .where(
            Booking.status == "confirmed",
        )
        .where(
            # Past date OR (today AND end_time already passed)
            (Booking.date < today)
            | ((Booking.date == today) & (Booking.end_time <= current_time))
        )
    )

    result = await session.execute(stmt)
    overdue_bookings = result.scalars().all()

    if not overdue_bookings:
        logger.info("No-show marker: 0 overdue bookings found")
        return 0

    # Update status in bulk
    booking_ids = [b.id for b in overdue_bookings]
    await session.execute(
        update(Booking)
        .where(Booking.id.in_(booking_ids))
        .values(status="no_show")
    )
    await session.flush()

    # Refresh to get updated status
    for b in overdue_bookings:
        await session.refresh(b)

    # Emit notification events
    if hub is not None:
        for b in overdue_bookings:
            await hub.emit(
                "appointment.no_show",
                {"booking_id": str(b.id)},
            )

    count = len(overdue_bookings)
    logger.info("No-show marker: marked %d bookings as no_show", count)
    return count
