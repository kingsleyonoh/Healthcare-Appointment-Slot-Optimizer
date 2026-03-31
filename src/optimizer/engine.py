"""Slot computation engine — main orchestrator for the Slot Optimizer.

Queries the database for providers, availability, bookings, rooms, and
overbooking rules, then delegates to constraints and scorer modules to
produce a sorted list of candidate appointment slots.
"""

from __future__ import annotations

import logging
from datetime import date, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import (
    AppointmentType,
    Booking,
    OverbookingRule,
    Provider,
    ProviderAvailability,
    Room,
)
from src.lib.time_utils import generate_slots
from src.optimizer.constraints import (
    apply_buffer,
    check_max_daily,
    check_room_availability,
    filter_compatible_rooms,
    get_availability_windows,
    subtract_bookings,
)
from src.optimizer.scorer import score_slot

logger = logging.getLogger(__name__)


async def find_available_slots(
    session: AsyncSession,
    target_date: date,
    appointment_type_id: str,
    provider_id: str | None = None,
    preferred_start: time | None = None,
    preferred_end: time | None = None,
) -> list[dict]:
    """Compute available appointment slots for a given date and type.

    Returns a list of slot dicts sorted by quality_score descending.
    """
    settings = get_settings()

    # 1. Load appointment type
    appt_type = await session.get(AppointmentType, appointment_type_id)
    if appt_type is None:
        return []

    duration = appt_type.duration_minutes
    required_type = appt_type.required_room_type
    required_equip = appt_type.required_equipment or []

    # 2. Load applicable providers
    provider_q = select(Provider).where(Provider.enabled.is_(True))
    if provider_id:
        provider_q = provider_q.where(Provider.id == provider_id)
    providers = (await session.execute(provider_q)).scalars().all()

    # 3. Load compatible rooms
    all_rooms = (
        await session.execute(select(Room).where(Room.enabled.is_(True)))
    ).scalars().all()
    compatible_rooms = filter_compatible_rooms(
        all_rooms, required_type, required_equip
    )
    if not compatible_rooms:
        return []

    # 4. Load overbooking rules
    overbook_rules = (
        await session.execute(
            select(OverbookingRule).where(OverbookingRule.enabled.is_(True))
        )
    ).scalars().all()

    slots: list[dict] = []

    for provider in providers:
        # 4a. Load availability windows
        avail_rows = (
            await session.execute(
                select(ProviderAvailability).where(
                    ProviderAvailability.provider_id == provider.id
                )
            )
        ).scalars().all()

        windows = get_availability_windows(avail_rows, target_date)
        if not windows:
            continue

        # 4b. Load existing bookings for this provider+date
        provider_bookings = (
            await session.execute(
                select(Booking).where(
                    Booking.provider_id == provider.id,
                    Booking.date == target_date,
                    Booking.status != "cancelled",
                )
            )
        ).scalars().all()

        # 4c. Check max daily limit
        booking_count = len(provider_bookings)
        is_maxed = check_max_daily(
            booking_count, provider.max_daily_appointments
        )

        # 4d. Subtract bookings from windows
        open_intervals = subtract_bookings(windows, provider_bookings)

        # 4e. Apply buffer
        open_intervals = apply_buffer(open_intervals, provider.buffer_minutes)

        if not open_intervals and not _get_max_overbook(
            overbook_rules, provider.id, appointment_type_id
        ):
            continue

        # 4f. Track rooms used by this provider today
        provider_rooms_used = list(
            {str(b.room_id) for b in provider_bookings}
        )

        # 4g. Generate candidate slots per room
        for room in compatible_rooms:
            # Load room bookings for the date
            room_bookings = (
                await session.execute(
                    select(Booking).where(
                        Booking.room_id == room.id,
                        Booking.date == target_date,
                        Booking.status != "cancelled",
                    )
                )
            ).scalars().all()

            for window in open_intervals:
                room_free = check_room_availability(window, room_bookings)
                for free_interval in room_free:
                    candidates = generate_slots(
                        start=free_interval[0],
                        end=free_interval[1],
                        duration_minutes=duration,
                        increment_minutes=settings.SLOT_INCREMENT_MINUTES,
                    )
                    for slot_start, slot_end in candidates:
                        if is_maxed:
                            continue  # Skip non-overbooked slots if maxed

                        quality = score_slot(
                            slot_start=slot_start,
                            slot_end=slot_end,
                            provider_bookings=provider_bookings,
                            preferred_start=preferred_start,
                            preferred_end=preferred_end,
                            provider_rooms_used=provider_rooms_used,
                            room_id=str(room.id),
                            is_overbooked=False,
                        )
                        slots.append({
                            "start": slot_start.isoformat(),
                            "end": slot_end.isoformat(),
                            "provider_id": str(provider.id),
                            "provider_name": provider.name,
                            "room_id": str(room.id),
                            "room_name": room.name,
                            "quality_score": quality,
                            "is_overbooked": False,
                        })

        # 4h. Overbooking slots
        max_overbook = _get_max_overbook(
            overbook_rules, provider.id, appointment_type_id
        )
        if max_overbook > 0 and booking_count < (
            provider.max_daily_appointments + max_overbook
        ):
            for room in compatible_rooms:
                for window in open_intervals if open_intervals else windows:
                    candidates = generate_slots(
                        start=window[0],
                        end=window[1],
                        duration_minutes=duration,
                        increment_minutes=settings.SLOT_INCREMENT_MINUTES,
                    )
                    for slot_start, slot_end in candidates:
                        # Only add overbooked slots not already in normal
                        slot_key = (
                            slot_start.isoformat(),
                            str(provider.id),
                            str(room.id),
                        )
                        existing_keys = {
                            (s["start"], s["provider_id"], s["room_id"])
                            for s in slots
                        }
                        if slot_key in existing_keys:
                            continue

                        quality = score_slot(
                            slot_start=slot_start,
                            slot_end=slot_end,
                            provider_bookings=provider_bookings,
                            preferred_start=preferred_start,
                            preferred_end=preferred_end,
                            provider_rooms_used=provider_rooms_used,
                            room_id=str(room.id),
                            is_overbooked=True,
                        )
                        slots.append({
                            "start": slot_start.isoformat(),
                            "end": slot_end.isoformat(),
                            "provider_id": str(provider.id),
                            "provider_name": provider.name,
                            "room_id": str(room.id),
                            "room_name": room.name,
                            "quality_score": quality,
                            "is_overbooked": True,
                        })

    # 5. Sort by quality score descending
    slots.sort(key=lambda s: s["quality_score"], reverse=True)
    return slots


async def find_next_available_date(
    session: AsyncSession,
    appointment_type_id: str,
    start_date: date,
    max_days: int = 14,
) -> date | None:
    """Scan forward up to *max_days* to find the next date with slots."""
    for offset in range(1, max_days + 1):
        check_date = start_date + timedelta(days=offset)
        result = await find_available_slots(
            session, check_date, appointment_type_id
        )
        if result:
            return check_date
    return None


def _get_max_overbook(
    rules: list,
    provider_id: str,
    appointment_type_id: str,
) -> int:
    """Find applicable max_overbook value from overbooking rules.

    Priority: provider+type specific > provider-only > global.
    """
    best = 0
    for rule in rules:
        # Provider + type specific
        if (
            rule.provider_id
            and str(rule.provider_id) == str(provider_id)
            and rule.appointment_type_id
            and str(rule.appointment_type_id) == str(appointment_type_id)
        ):
            return rule.max_overbook
        # Provider-only
        if (
            rule.provider_id
            and str(rule.provider_id) == str(provider_id)
            and not rule.appointment_type_id
        ):
            best = max(best, rule.max_overbook)
        # Global
        if not rule.provider_id and not rule.appointment_type_id:
            best = max(best, rule.max_overbook)
    return best
