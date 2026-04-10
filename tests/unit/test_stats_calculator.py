"""Unit tests for the Stats Calculator background job.

Tests run against the real local PostgreSQL (port 5434).
"""

from __future__ import annotations

import uuid
from datetime import date, time, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AppointmentType,
    Booking,
    Provider,
    ProviderAvailability,
    Room,
)
from src.jobs.stats_calculator import calculate_stats, StatsSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_provider(session: AsyncSession, **overrides) -> Provider:
    defaults = {
        "name": f"Dr. Stats-{uuid.uuid4().hex[:6]}",
        "specialty": "General",
        "max_daily_appointments": 20,
        "buffer_minutes": 10,
        "enabled": True,
    }
    defaults.update(overrides)
    p = Provider(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_room(session: AsyncSession, **overrides) -> Room:
    defaults = {
        "name": f"Room-{uuid.uuid4().hex[:6]}",
        "room_type": "consultation",
        "equipment": [],
        "enabled": True,
    }
    defaults.update(overrides)
    r = Room(**defaults)
    session.add(r)
    await session.flush()
    return r


async def _seed_appt_type(session: AsyncSession, **overrides) -> AppointmentType:
    defaults = {
        "name": f"Type-{uuid.uuid4().hex[:6]}",
        "duration_minutes": 30,
        "required_room_type": "consultation",
        "required_equipment": [],
        "enabled": True,
    }
    defaults.update(overrides)
    a = AppointmentType(**defaults)
    session.add(a)
    await session.flush()
    return a


async def _seed_availability(
    session: AsyncSession,
    provider_id,
    day_of_week: int,
    start_time: time = time(8, 0),
    end_time: time = time(17, 0),
) -> ProviderAvailability:
    avail = ProviderAvailability(
        provider_id=provider_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
    )
    session.add(avail)
    await session.flush()
    return avail


async def _create_booking(
    session: AsyncSession,
    provider: Provider,
    room: Room,
    appt_type: AppointmentType,
    target_date: date,
    start_time: time,
    status: str = "confirmed",
) -> Booking:
    end_minutes = start_time.hour * 60 + start_time.minute + appt_type.duration_minutes
    end_time = time(end_minutes // 60, end_minutes % 60)
    booking = Booking(
        request_id=f"req-stats-{uuid.uuid4().hex[:8]}",
        patient_name="Stats Patient",
        provider_id=provider.id,
        room_id=room.id,
        appointment_type_id=appt_type.id,
        date=target_date,
        start_time=start_time,
        end_time=end_time,
        status=status,
    )
    session.add(booking)
    await session.flush()
    return booking


# ---------------------------------------------------------------------------
# Tests — Stats Calculator
# ---------------------------------------------------------------------------


class TestCalculateStats:
    """Tests for calculate_stats() function."""

    async def test_returns_stats_snapshot_type(self, async_session):
        """Result is a StatsSnapshot dataclass."""
        result = await calculate_stats(session=async_session)
        assert isinstance(result, StatsSnapshot)

    async def test_bookings_today_counts_confirmed_bookings(self, async_session):
        """bookings_today counts confirmed bookings on current date."""
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        today = date.today()

        await _create_booking(
            async_session, provider, room, appt_type,
            target_date=today, start_time=time(9, 0), status="confirmed",
        )
        room2 = await _seed_room(async_session)
        await _create_booking(
            async_session, provider, room2, appt_type,
            target_date=today, start_time=time(10, 0), status="confirmed",
        )

        result = await calculate_stats(session=async_session)

        assert result.bookings_today == 2

    async def test_bookings_today_excludes_cancelled(self, async_session):
        """Cancelled bookings are not counted in bookings_today."""
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        today = date.today()

        await _create_booking(
            async_session, provider, room, appt_type,
            target_date=today, start_time=time(9, 0), status="cancelled",
        )

        result = await calculate_stats(session=async_session)

        assert result.bookings_today == 0

    async def test_no_shows_counts_no_show_bookings_today(self, async_session):
        """no_shows counts bookings with status no_show on current date."""
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        today = date.today()

        await _create_booking(
            async_session, provider, room, appt_type,
            target_date=today, start_time=time(9, 0), status="no_show",
        )

        result = await calculate_stats(session=async_session)

        assert result.no_shows == 1

    async def test_no_shows_excludes_other_statuses(self, async_session):
        """Only no_show status counts in no_shows."""
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        today = date.today()

        await _create_booking(
            async_session, provider, room, appt_type,
            target_date=today, start_time=time(9, 0), status="confirmed",
        )

        result = await calculate_stats(session=async_session)

        assert result.no_shows == 0

    async def test_utilization_with_bookings_and_availability(self, async_session):
        """utilization_today is slots_used/slots_available for today."""
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session, duration_minutes=30)
        today = date.today()
        dow = today.weekday()

        # Provider available 09:00-12:00 today = 3h = 12 slots at 15min
        await _seed_availability(
            async_session, provider.id, dow,
            start_time=time(9, 0), end_time=time(12, 0),
        )

        # 2 confirmed bookings
        await _create_booking(
            async_session, provider, room, appt_type,
            target_date=today, start_time=time(9, 0), status="confirmed",
        )
        room2 = await _seed_room(async_session)
        await _create_booking(
            async_session, provider, room2, appt_type,
            target_date=today, start_time=time(10, 0), status="confirmed",
        )

        result = await calculate_stats(session=async_session)

        # 2 bookings / 12 available slots ≈ 0.1667
        assert 0.0 < result.utilization_today < 1.0
        assert abs(result.utilization_today - 2 / 12) < 0.01

    async def test_utilization_zero_when_no_availability(self, async_session):
        """utilization_today is 0.0 when no provider has availability today."""
        result = await calculate_stats(session=async_session)

        assert result.utilization_today == 0.0

    async def test_utilization_zero_when_no_bookings(self, async_session):
        """utilization_today is 0.0 when availability exists but no bookings."""
        provider = await _seed_provider(async_session)
        today = date.today()
        dow = today.weekday()

        await _seed_availability(
            async_session, provider.id, dow,
            start_time=time(9, 0), end_time=time(17, 0),
        )

        result = await calculate_stats(session=async_session)

        assert result.utilization_today == 0.0

    async def test_stats_for_empty_database(self, async_session):
        """Empty database returns all zeros."""
        result = await calculate_stats(session=async_session)

        assert result.utilization_today == 0.0
        assert result.bookings_today == 0
        assert result.no_shows == 0
