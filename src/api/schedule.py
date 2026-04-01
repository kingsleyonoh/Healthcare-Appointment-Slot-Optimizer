"""Schedule View API route — GET /api/schedule.

Returns a daily breakdown of bookings, gaps, and utilization per provider
across a date range. Protected by API-key auth.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import create_api_key_dependency
from src.api.schemas.schedule_schemas import (
    ProviderDaySchedule,
    ScheduleBooking,
    ScheduleGap,
    ScheduleResponse,
    ScheduleSummary,
)
from src.config import get_settings
from src.db.models import (
    AppointmentType,
    Booking,
    Provider,
    ProviderAvailability,
    Room,
)
from src.db.session import get_session
from src.lib.errors import AppError
from src.lib.time_utils import time_to_minutes
from src.optimizer.constraints import get_availability_windows

logger = logging.getLogger(__name__)

settings = get_settings()
router = APIRouter(prefix="/api", tags=["schedule"])
_auth = create_api_key_dependency(settings.api_keys_list)


def _compute_gaps(
    bookings: list[Booking],
    window_start: time,
    window_end: time,
) -> list[ScheduleGap]:
    """Find gaps between bookings within an availability window."""
    sorted_bookings = sorted(bookings, key=lambda b: b.start_time)
    gaps: list[ScheduleGap] = []
    cursor = time_to_minutes(window_start)
    window_end_mins = time_to_minutes(window_end)

    for b in sorted_bookings:
        b_start = time_to_minutes(b.start_time)
        if b_start > cursor:
            gap_mins = b_start - cursor
            gaps.append(ScheduleGap(
                start_time=_minutes_to_time(cursor),
                end_time=b.start_time,
                duration_minutes=gap_mins,
            ))
        b_end = time_to_minutes(b.end_time)
        cursor = max(cursor, b_end)

    if cursor < window_end_mins:
        gaps.append(ScheduleGap(
            start_time=_minutes_to_time(cursor),
            end_time=window_end,
            duration_minutes=window_end_mins - cursor,
        ))

    return gaps


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


def _minutes_to_time(minutes: int) -> time:
    return time(minutes // 60, minutes % 60)


@router.get("/schedule")
async def get_schedule(
    date_from: date = Query(...),
    date_to: date = Query(...),
    provider_id: str | None = Query(None),
    room_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> ScheduleResponse:
    """Return schedule view with utilization for a date range."""
    if date_to < date_from:
        raise AppError(
            code="VALIDATION_ERROR",
            message="date_to must be on or after date_from",
            status_code=400,
        )

    # Load providers
    provider_q = select(Provider).where(Provider.enabled.is_(True))
    if provider_id:
        provider_q = provider_q.where(Provider.id == provider_id)
    providers = (await session.execute(provider_q)).scalars().all()

    # Load all availability for these providers
    provider_ids = [p.id for p in providers]
    avail_rows = (
        await session.execute(
            select(ProviderAvailability).where(
                ProviderAvailability.provider_id.in_(provider_ids)
            )
        )
    ).scalars().all() if provider_ids else []

    # Load bookings in date range
    booking_q = (
        select(Booking)
        .where(
            Booking.date >= date_from,
            Booking.date <= date_to,
            Booking.status != "cancelled",
        )
    )
    if provider_id:
        booking_q = booking_q.where(Booking.provider_id == provider_id)
    if room_id:
        booking_q = booking_q.where(Booking.room_id == room_id)
    all_bookings = (await session.execute(booking_q)).scalars().all()

    # Load appointment types and rooms for display names
    appt_types = {
        a.id: a.name
        for a in (await session.execute(select(AppointmentType))).scalars().all()
    }
    rooms = {
        r.id: r.name
        for r in (await session.execute(select(Room))).scalars().all()
    }

    # Build schedule entries per provider × date
    schedule: list[ProviderDaySchedule] = []
    slot_minutes = settings.SLOT_INCREMENT_MINUTES

    current = date_from
    while current <= date_to:
        for provider in providers:
            # Filter availability for this provider on this date
            p_avail = [a for a in avail_rows if a.provider_id == provider.id]
            windows = get_availability_windows(p_avail, current)
            if not windows:
                current += timedelta(days=1)
                continue

            # Filter bookings for this provider on this date
            day_bookings = [
                b for b in all_bookings
                if b.provider_id == provider.id and b.date == current
            ]

            # Build booking summaries
            booking_items = [
                ScheduleBooking(
                    id=b.id,
                    patient_name=b.patient_name,
                    start_time=b.start_time,
                    end_time=b.end_time,
                    status=b.status,
                    appointment_type=appt_types.get(b.appointment_type_id, "Unknown"),
                    room_name=rooms.get(b.room_id, "Unknown"),
                )
                for b in sorted(day_bookings, key=lambda x: x.start_time)
            ]

            # Compute gaps across all windows
            all_gaps: list[ScheduleGap] = []
            for w_start, w_end in windows:
                w_bookings = [
                    b for b in day_bookings
                    if b.start_time >= w_start and b.end_time <= w_end
                ]
                all_gaps.extend(_compute_gaps(w_bookings, w_start, w_end))

            # Utilization
            total_slots = _count_available_slots(windows, slot_minutes)
            utilization = (
                len(day_bookings) / total_slots if total_slots > 0 else 0.0
            )
            utilization = min(utilization, 1.0)

            schedule.append(ProviderDaySchedule(
                date=current,
                provider_id=str(provider.id),
                provider_name=provider.name,
                bookings=booking_items,
                gaps=all_gaps,
                utilization=round(utilization, 4),
            ))

        current += timedelta(days=1)

    # Summary
    total_util = (
        sum(s.utilization for s in schedule) / len(schedule)
        if schedule else 0.0
    )

    return ScheduleResponse(
        schedule=schedule,
        summary=ScheduleSummary(total_utilization=round(total_util, 4)),
    )
