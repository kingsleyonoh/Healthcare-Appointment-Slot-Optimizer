"""Unit tests for the booking service layer."""

import uuid
from datetime import date, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.service import cancel_booking, create_booking, get_booking, list_bookings
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


# ---------------------------------------------------------------------------
# Helpers — create a confirmed booking for cancel/list/get tests
# ---------------------------------------------------------------------------


async def _create_confirmed_booking(
    session: AsyncSession, request_id: str, start_hour: int = 9, **overrides
) -> Booking:
    """Seed provider/room/type/availability and create a confirmed booking."""
    provider = overrides.pop("provider", None) or await _seed_provider(session)
    room = overrides.pop("room", None) or await _seed_room(session)
    appt_type = overrides.pop("appt_type", None) or await _seed_appt_type(session)
    target_date = overrides.pop("target_date", None) or _next_weekday(0)
    if not overrides.pop("skip_availability", False):
        await _seed_availability(session, provider.id, day_of_week=target_date.weekday())

    booking, _ = await create_booking(
        session=session,
        request_id=request_id,
        patient_name=overrides.get("patient_name", "Test Patient"),
        provider_id=provider.id,
        room_id=room.id,
        appointment_type_id=appt_type.id,
        target_date=target_date,
        start_time=time(start_hour, 0),
    )
    return booking


# ---------------------------------------------------------------------------
# Tests — Get Booking
# ---------------------------------------------------------------------------


class TestGetBooking:
    """Tests for retrieving a single booking by ID."""

    async def test_get_existing_booking_returns_it(self, async_session):
        booking = await _create_confirmed_booking(async_session, "req-get-1")

        result = await get_booking(session=async_session, booking_id=booking.id)

        assert result.id == booking.id
        assert result.request_id == "req-get-1"

    async def test_get_nonexistent_booking_raises_not_found(self, async_session):
        with pytest.raises(AppError) as exc_info:
            await get_booking(session=async_session, booking_id=uuid.uuid4())

        assert exc_info.value.code == "NOT_FOUND"
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests — List Bookings
# ---------------------------------------------------------------------------


class TestListBookings:
    """Tests for listing bookings with filters."""

    async def test_list_returns_all_bookings(self, async_session):
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)
        target_date = _next_weekday(0)
        await _seed_availability(async_session, provider.id, day_of_week=0)

        for i, hour in enumerate([9, 10, 11]):
            await create_booking(
                session=async_session,
                request_id=f"req-list-{i}",
                patient_name=f"Patient {i}",
                provider_id=provider.id,
                room_id=room.id,
                appointment_type_id=appt_type.id,
                target_date=target_date,
                start_time=time(hour, 0),
            )

        from src.lib.pagination import PaginationParams
        bookings, total = await list_bookings(
            session=async_session,
            pagination=PaginationParams(),
        )

        assert total >= 3
        assert len(bookings) >= 3

    async def test_list_filters_by_status(self, async_session):
        booking = await _create_confirmed_booking(async_session, "req-list-status")

        from src.lib.pagination import PaginationParams
        confirmed, total_c = await list_bookings(
            session=async_session,
            status="confirmed",
            pagination=PaginationParams(),
        )
        cancelled, total_x = await list_bookings(
            session=async_session,
            status="cancelled",
            pagination=PaginationParams(),
        )

        assert any(b.id == booking.id for b in confirmed)
        assert not any(b.id == booking.id for b in cancelled)

    async def test_list_filters_by_provider_id(self, async_session):
        booking = await _create_confirmed_booking(async_session, "req-list-prov")

        from src.lib.pagination import PaginationParams
        matched, total = await list_bookings(
            session=async_session,
            provider_id=booking.provider_id,
            pagination=PaginationParams(),
        )
        unmatched, total2 = await list_bookings(
            session=async_session,
            provider_id=uuid.uuid4(),
            pagination=PaginationParams(),
        )

        assert any(b.id == booking.id for b in matched)
        assert total2 == 0


# ---------------------------------------------------------------------------
# Tests — Cancel Booking
# ---------------------------------------------------------------------------


class TestCancelBooking:
    """Tests for booking cancellation."""

    async def test_cancel_sets_status_and_reason(self, async_session):
        booking = await _create_confirmed_booking(async_session, "req-cancel-1")

        cancelled = await cancel_booking(
            session=async_session,
            booking_id=booking.id,
            reason="Patient requested",
        )

        assert cancelled.status == "cancelled"
        assert cancelled.cancellation_reason == "Patient requested"

    async def test_cancel_already_cancelled_is_idempotent(self, async_session):
        booking = await _create_confirmed_booking(async_session, "req-cancel-idem")

        first = await cancel_booking(
            session=async_session, booking_id=booking.id, reason="First cancel"
        )
        second = await cancel_booking(
            session=async_session, booking_id=booking.id, reason="Second cancel"
        )

        assert first.id == second.id
        assert second.status == "cancelled"
        # Reason stays from first cancellation
        assert second.cancellation_reason == "First cancel"

    async def test_cancel_completed_booking_raises_error(self, async_session):
        booking = await _create_confirmed_booking(async_session, "req-cancel-done")
        # Manually set status to completed
        booking.status = "completed"
        await async_session.flush()

        with pytest.raises(AppError) as exc_info:
            await cancel_booking(
                session=async_session, booking_id=booking.id, reason="Too late"
            )

        assert exc_info.value.code == "VALIDATION_ERROR"
        assert exc_info.value.status_code == 400

    async def test_cancel_no_show_booking_raises_error(self, async_session):
        booking = await _create_confirmed_booking(async_session, "req-cancel-noshow")
        booking.status = "no_show"
        await async_session.flush()

        with pytest.raises(AppError) as exc_info:
            await cancel_booking(
                session=async_session, booking_id=booking.id, reason="Changed mind"
            )

        assert exc_info.value.code == "VALIDATION_ERROR"

    async def test_cancel_nonexistent_booking_raises_not_found(self, async_session):
        with pytest.raises(AppError) as exc_info:
            await cancel_booking(
                session=async_session, booking_id=uuid.uuid4(), reason="N/A"
            )

        assert exc_info.value.code == "NOT_FOUND"
        assert exc_info.value.status_code == 404
