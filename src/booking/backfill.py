"""Backfill candidate query — find cancelled bookings that could fill a freed slot.

When a booking is cancelled, this module queries for other cancelled bookings
with the same appointment type within ±7 days. These represent patients who
lost their appointments and might want the freed slot.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AppointmentType, Booking

_SEARCH_WINDOW_DAYS = 7


async def find_backfill_candidates(
    *,
    session: AsyncSession,
    cancelled_booking: Booking,
) -> list[dict]:
    """Find cancelled bookings that could backfill a freed slot.

    Searches for cancelled bookings with the same appointment type
    within ±7 days of the cancelled booking's date.

    Returns a list of dicts sorted by time_proximity_score (descending):
        - candidate_booking_id (UUID)
        - patient_name (str)
        - appointment_type (str)
        - time_proximity_score (float, 0.0–1.0)
    """
    date_from = cancelled_booking.date - timedelta(days=_SEARCH_WINDOW_DAYS)
    date_to = cancelled_booking.date + timedelta(days=_SEARCH_WINDOW_DAYS)

    rows = (
        await session.execute(
            select(Booking, AppointmentType.name.label("appt_name"))
            .join(AppointmentType, Booking.appointment_type_id == AppointmentType.id)
            .where(
                Booking.status == "cancelled",
                Booking.appointment_type_id == cancelled_booking.appointment_type_id,
                Booking.id != cancelled_booking.id,
                Booking.date >= date_from,
                Booking.date <= date_to,
            )
            .order_by(Booking.date)
        )
    ).all()

    candidates: list[dict] = []
    for booking, appt_name in rows:
        days_diff = abs((booking.date - cancelled_booking.date).days)
        score = round(1.0 - (days_diff / _SEARCH_WINDOW_DAYS), 2)
        candidates.append(
            {
                "candidate_booking_id": booking.id,
                "patient_name": booking.patient_name,
                "appointment_type": appt_name,
                "time_proximity_score": score,
            }
        )

    candidates.sort(key=lambda c: c["time_proximity_score"], reverse=True)
    return candidates
