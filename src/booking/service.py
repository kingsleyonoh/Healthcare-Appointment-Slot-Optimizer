"""Booking service — business logic for creating bookings.

Separates domain logic from API routes per PRD §9 architecture.
"""

from __future__ import annotations

import logging
from datetime import date, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AppointmentType,
    Booking,
    Provider,
    ProviderAvailability,
    Room,
)
from src.lib.errors import AppError

logger = logging.getLogger(__name__)


def _add_minutes(t: time, minutes: int) -> time:
    """Add *minutes* to a ``time`` object, returning a new ``time``."""
    total = t.hour * 60 + t.minute + minutes
    return time(total // 60, total % 60)


async def create_booking(
    *,
    session: AsyncSession,
    request_id: str,
    patient_name: str,
    provider_id,
    room_id,
    appointment_type_id,
    target_date: date,
    start_time: time,
    patient_email: str | None = None,
) -> tuple[Booking, bool]:
    """Create a booking with full validation.

    Returns ``(booking, is_new)`` — *is_new* is ``False`` when an
    existing booking with the same *request_id* is found (idempotent).

    Raises :class:`AppError` on validation failure or conflict.
    """
    # --- Idempotency check ---
    existing = (
        await session.execute(
            select(Booking).where(Booking.request_id == request_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    # --- Load and validate appointment type ---
    appt_type = await session.get(AppointmentType, appointment_type_id)
    if appt_type is None:
        raise AppError(
            code="NOT_FOUND",
            message=f"Appointment type {appointment_type_id} not found",
            status_code=404,
        )

    end_time = _add_minutes(start_time, appt_type.duration_minutes)

    # --- Load and validate provider ---
    provider = await session.get(Provider, provider_id)
    if provider is None:
        raise AppError(
            code="NOT_FOUND",
            message=f"Provider {provider_id} not found",
            status_code=404,
        )
    if not provider.enabled:
        raise AppError(
            code="VALIDATION_ERROR",
            message=f"Provider {provider.name} is disabled",
            status_code=400,
        )

    # --- Load and validate room ---
    room = await session.get(Room, room_id)
    if room is None:
        raise AppError(
            code="NOT_FOUND",
            message=f"Room {room_id} not found",
            status_code=404,
        )

    # --- Check availability window ---
    day_of_week = target_date.weekday()
    windows = (
        await session.execute(
            select(ProviderAvailability).where(
                ProviderAvailability.provider_id == provider_id,
                ProviderAvailability.day_of_week == day_of_week,
                ProviderAvailability.valid_from <= target_date,
                ProviderAvailability.valid_until >= target_date,
            )
        )
    ).scalars().all()

    in_window = any(
        w.start_time <= start_time and w.end_time >= end_time for w in windows
    )
    if not in_window:
        raise AppError(
            code="VALIDATION_ERROR",
            message=(
                f"Requested time {start_time}–{end_time} on "
                f"{target_date} is outside provider availability"
            ),
            status_code=400,
        )

    # --- Check max daily appointments ---
    daily_count = (
        await session.execute(
            select(func.count(Booking.id)).where(
                Booking.provider_id == provider_id,
                Booking.date == target_date,
                Booking.status != "cancelled",
            )
        )
    ).scalar_one()

    if daily_count >= provider.max_daily_appointments:
        raise AppError(
            code="CONFLICT",
            message=(
                f"Provider {provider.name} has reached the maximum "
                f"of {provider.max_daily_appointments} appointments for {target_date}"
            ),
            status_code=409,
        )

    # --- Insert booking (DB constraints prevent double-booking) ---
    booking = Booking(
        request_id=request_id,
        patient_name=patient_name,
        patient_email=patient_email,
        provider_id=provider_id,
        room_id=room_id,
        appointment_type_id=appointment_type_id,
        date=target_date,
        start_time=start_time,
        end_time=end_time,
        status="confirmed",
    )
    session.add(booking)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise AppError(
            code="SLOT_UNAVAILABLE",
            message="The requested slot is no longer available",
            status_code=409,
        )

    await session.refresh(booking)
    return booking, True
