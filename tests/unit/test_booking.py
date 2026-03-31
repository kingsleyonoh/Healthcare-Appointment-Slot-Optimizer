"""Unit tests for the booking service layer."""

from datetime import date, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.service import create_booking
from src.db.models import (
    AppointmentType,
    Booking,
    Provider,
    ProviderAvailability,
    Room,
)
from src.lib.errors import AppError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_provider(session: AsyncSession, **overrides) -> Provider:
    defaults = {
        "name": "Dr. Test",
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
    defaults = {"name": "Room A", "room_type": "consultation", "equipment": [], "enabled": True}
    defaults.update(overrides)
    r = Room(**defaults)
    session.add(r)
    await session.flush()
    return r


async def _seed_appt_type(session: AsyncSession, **overrides) -> AppointmentType:
    defaults = {
        "name": "Checkup",
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


async def _seed_availability(session: AsyncSession, provider_id, day_of_week=0):
    avail = ProviderAvailability(
        provider_id=provider_id,
        day_of_week=day_of_week,
        start_time=time(8, 0),
        end_time=time(17, 0),
    )
    session.add(avail)
    await session.flush()
    return avail


def _next_weekday(dow: int = 0) -> date:
    """Return the next date matching day_of_week (0=Mon)."""
    today = date.today()
    days_ahead = dow - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


# ---------------------------------------------------------------------------
# Tests — Happy Path
# ---------------------------------------------------------------------------


class TestCreateBookingHappyPath:
    """Tests for successful booking creation."""

    async def test_creates_booking_with_correct_fields(self, async_session):
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        target_date = _next_weekday(0)  # Monday
        await _seed_availability(async_session, provider.id, day_of_week=0)

        booking, is_new = await create_booking(
            session=async_session,
            request_id="req-001",
            patient_name="Alice",
            patient_email="alice@example.com",
            provider_id=provider.id,
            room_id=room.id,
            appointment_type_id=appt_type.id,
            target_date=target_date,
            start_time=time(9, 0),
        )

        assert is_new is True
        assert booking.request_id == "req-001"
        assert booking.patient_name == "Alice"
        assert booking.provider_id == provider.id
        assert booking.room_id == room.id
        assert booking.status == "confirmed"

    async def test_end_time_derived_from_appointment_duration(self, async_session):
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session, duration_minutes=45)
        target_date = _next_weekday(0)
        await _seed_availability(async_session, provider.id, day_of_week=0)

        booking, _ = await create_booking(
            session=async_session,
            request_id="req-002",
            patient_name="Bob",
            provider_id=provider.id,
            room_id=room.id,
            appointment_type_id=appt_type.id,
            target_date=target_date,
            start_time=time(10, 0),
        )

        assert booking.end_time == time(10, 45)


# ---------------------------------------------------------------------------
# Tests — Idempotency
# ---------------------------------------------------------------------------


class TestIdempotentBooking:
    """Duplicate request_id returns existing booking."""

    async def test_duplicate_request_id_returns_existing(self, async_session):
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        target_date = _next_weekday(0)
        await _seed_availability(async_session, provider.id, day_of_week=0)

        kwargs = dict(
            session=async_session,
            request_id="req-dup",
            patient_name="Carol",
            provider_id=provider.id,
            room_id=room.id,
            appointment_type_id=appt_type.id,
            target_date=target_date,
            start_time=time(11, 0),
        )

        first, first_new = await create_booking(**kwargs)
        second, second_new = await create_booking(**kwargs)

        assert first_new is True
        assert second_new is False
        assert first.id == second.id
        assert first.request_id == second.request_id

    async def test_duplicate_does_not_create_second_row(self, async_session):
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        target_date = _next_weekday(0)
        await _seed_availability(async_session, provider.id, day_of_week=0)

        kwargs = dict(
            session=async_session,
            request_id="req-dup2",
            patient_name="Dan",
            provider_id=provider.id,
            room_id=room.id,
            appointment_type_id=appt_type.id,
            target_date=target_date,
            start_time=time(12, 0),
        )

        await create_booking(**kwargs)  # first
        await create_booking(**kwargs)  # duplicate

        count = (
            await async_session.execute(
                select(Booking).where(Booking.request_id == "req-dup2")
            )
        ).scalars().all()
        assert len(count) == 1


# ---------------------------------------------------------------------------
# Tests — Validation / Error Paths
# ---------------------------------------------------------------------------


class TestBookingValidation:
    """Tests for rejection of invalid bookings."""

    async def test_nonexistent_provider_raises_not_found(self, async_session):
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        import uuid

        with pytest.raises(AppError) as exc_info:
            await create_booking(
                session=async_session,
                request_id="req-bad-prov",
                patient_name="Eve",
                provider_id=uuid.uuid4(),
                room_id=room.id,
                appointment_type_id=appt_type.id,
                target_date=_next_weekday(0),
                start_time=time(9, 0),
            )
        assert exc_info.value.code == "NOT_FOUND"

    async def test_nonexistent_room_raises_not_found(self, async_session):
        provider = await _seed_provider(async_session)
        appt_type = await _seed_appt_type(async_session)
        import uuid

        target_date = _next_weekday(0)
        await _seed_availability(async_session, provider.id, day_of_week=0)

        with pytest.raises(AppError) as exc_info:
            await create_booking(
                session=async_session,
                request_id="req-bad-room",
                patient_name="Frank",
                provider_id=provider.id,
                room_id=uuid.uuid4(),
                appointment_type_id=appt_type.id,
                target_date=target_date,
                start_time=time(9, 0),
            )
        assert exc_info.value.code == "NOT_FOUND"

    async def test_nonexistent_appointment_type_raises_not_found(self, async_session):
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        import uuid

        target_date = _next_weekday(0)
        await _seed_availability(async_session, provider.id, day_of_week=0)

        with pytest.raises(AppError) as exc_info:
            await create_booking(
                session=async_session,
                request_id="req-bad-type",
                patient_name="Grace",
                provider_id=provider.id,
                room_id=room.id,
                appointment_type_id=uuid.uuid4(),
                target_date=target_date,
                start_time=time(9, 0),
            )
        assert exc_info.value.code == "NOT_FOUND"

    async def test_outside_availability_window_raises_error(self, async_session):
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        # Provider available Mon only, book on Tuesday
        target_tue = _next_weekday(1)
        await _seed_availability(async_session, provider.id, day_of_week=0)

        with pytest.raises(AppError) as exc_info:
            await create_booking(
                session=async_session,
                request_id="req-no-avail",
                patient_name="Henry",
                provider_id=provider.id,
                room_id=room.id,
                appointment_type_id=appt_type.id,
                target_date=target_tue,
                start_time=time(9, 0),
            )
        assert exc_info.value.code == "VALIDATION_ERROR"

    async def test_booking_before_availability_start_raises_error(self, async_session):
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        target_date = _next_weekday(0)
        await _seed_availability(async_session, provider.id, day_of_week=0)

        with pytest.raises(AppError) as exc_info:
            await create_booking(
                session=async_session,
                request_id="req-early",
                patient_name="Iris",
                provider_id=provider.id,
                room_id=room.id,
                appointment_type_id=appt_type.id,
                target_date=target_date,
                start_time=time(6, 0),  # Before 08:00
            )
        assert exc_info.value.code == "VALIDATION_ERROR"

    async def test_max_daily_appointments_exceeded_raises_error(self, async_session):
        provider = await _seed_provider(async_session, max_daily_appointments=1)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session, duration_minutes=15)
        target_date = _next_weekday(0)
        await _seed_availability(async_session, provider.id, day_of_week=0)

        # First booking succeeds
        _, _ = await create_booking(
            session=async_session,
            request_id="req-max-1",
            patient_name="Jack",
            provider_id=provider.id,
            room_id=room.id,
            appointment_type_id=appt_type.id,
            target_date=target_date,
            start_time=time(9, 0),
        )

        # Second should fail — max is 1
        with pytest.raises(AppError) as exc_info:
            await create_booking(
                session=async_session,
                request_id="req-max-2",
                patient_name="Kate",
                provider_id=provider.id,
                room_id=room.id,
                appointment_type_id=appt_type.id,
                target_date=target_date,
                start_time=time(10, 0),
            )
        assert exc_info.value.code == "CONFLICT"

    async def test_disabled_provider_raises_error(self, async_session):
        provider = await _seed_provider(async_session, enabled=False)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        target_date = _next_weekday(0)
        await _seed_availability(async_session, provider.id, day_of_week=0)

        with pytest.raises(AppError) as exc_info:
            await create_booking(
                session=async_session,
                request_id="req-disabled",
                patient_name="Leo",
                provider_id=provider.id,
                room_id=room.id,
                appointment_type_id=appt_type.id,
                target_date=target_date,
                start_time=time(9, 0),
            )
        assert exc_info.value.code == "VALIDATION_ERROR"
