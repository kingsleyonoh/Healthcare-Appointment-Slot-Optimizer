"""Unit tests for the No-Show Marker background job.

Tests run against the real local PostgreSQL (port 5434).
No mocks for DB — see CODING_STANDARDS_TESTING.md Mock Policy.
The NotificationHubClient IS mocked because it's an external service.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AppointmentType,
    Booking,
    Provider,
    ProviderAvailability,
    Room,
)
from src.integrations.notification_hub import NotificationHubClient
from src.jobs.no_show_marker import mark_no_shows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_provider(session: AsyncSession, **overrides) -> Provider:
    defaults = {
        "name": "Dr. NoShow",
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


async def _create_booking(
    session: AsyncSession,
    provider: Provider,
    room: Room,
    appt_type: AppointmentType,
    target_date: date,
    start_time: time,
    status: str = "confirmed",
) -> Booking:
    """Create a booking directly via ORM (bypass service validation)."""
    end_minutes = start_time.hour * 60 + start_time.minute + appt_type.duration_minutes
    end_time = time(end_minutes // 60, end_minutes % 60)

    booking = Booking(
        request_id=f"req-ns-{uuid.uuid4().hex[:8]}",
        patient_name="Test Patient",
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
# Tests — No-Show Marker
# ---------------------------------------------------------------------------


class TestMarkNoShows:
    """Tests for mark_no_shows() — marks overdue confirmed bookings."""

    async def test_marks_overdue_confirmed_booking_as_no_show(self, async_session):
        """A confirmed booking whose end_time has passed gets marked no_show."""
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session, duration_minutes=30)

        # Yesterday at 09:00-09:30 — definitely overdue
        yesterday = date.today() - timedelta(days=1)
        booking = await _create_booking(
            async_session, provider, room, appt_type,
            target_date=yesterday,
            start_time=time(9, 0),
            status="confirmed",
        )

        count = await mark_no_shows(session=async_session)

        assert count == 1
        await async_session.refresh(booking)
        assert booking.status == "no_show"

    async def test_skips_already_cancelled_bookings(self, async_session):
        """Cancelled bookings are not marked as no_show."""
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)

        yesterday = date.today() - timedelta(days=1)
        booking = await _create_booking(
            async_session, provider, room, appt_type,
            target_date=yesterday,
            start_time=time(9, 0),
            status="cancelled",
        )

        count = await mark_no_shows(session=async_session)

        assert count == 0
        await async_session.refresh(booking)
        assert booking.status == "cancelled"

    async def test_skips_future_confirmed_bookings(self, async_session):
        """Confirmed bookings in the future are not marked as no_show."""
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)

        tomorrow = date.today() + timedelta(days=1)
        booking = await _create_booking(
            async_session, provider, room, appt_type,
            target_date=tomorrow,
            start_time=time(14, 0),
            status="confirmed",
        )

        count = await mark_no_shows(session=async_session)

        assert count == 0
        await async_session.refresh(booking)
        assert booking.status == "confirmed"

    async def test_skips_already_completed_bookings(self, async_session):
        """Completed bookings are not re-marked."""
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)

        yesterday = date.today() - timedelta(days=1)
        booking = await _create_booking(
            async_session, provider, room, appt_type,
            target_date=yesterday,
            start_time=time(9, 0),
            status="completed",
        )

        count = await mark_no_shows(session=async_session)

        assert count == 0
        await async_session.refresh(booking)
        assert booking.status == "completed"

    async def test_marks_multiple_overdue_bookings(self, async_session):
        """Multiple overdue confirmed bookings are all marked."""
        provider = await _seed_provider(async_session)
        appt_type = await _seed_appt_type(async_session, duration_minutes=30)
        yesterday = date.today() - timedelta(days=1)

        bookings = []
        for hour in [9, 10, 11]:
            room = await _seed_room(async_session)
            b = await _create_booking(
                async_session, provider, room, appt_type,
                target_date=yesterday,
                start_time=time(hour, 0),
                status="confirmed",
            )
            bookings.append(b)

        count = await mark_no_shows(session=async_session)

        assert count == 3
        for b in bookings:
            await async_session.refresh(b)
            assert b.status == "no_show"

    async def test_returns_zero_when_no_overdue_bookings(self, async_session):
        """No overdue bookings returns count of 0."""
        count = await mark_no_shows(session=async_session)
        assert count == 0

    async def test_emits_no_show_event_for_each_marked_booking(self, async_session):
        """Each marked booking triggers an appointment.no_show event."""
        provider = await _seed_provider(async_session)
        room = await _seed_room(async_session)
        appt_type = await _seed_appt_type(async_session)

        yesterday = date.today() - timedelta(days=1)
        booking = await _create_booking(
            async_session, provider, room, appt_type,
            target_date=yesterday,
            start_time=time(9, 0),
            status="confirmed",
        )

        hub = NotificationHubClient(
            url="http://hub.test", api_key="test-key", enabled=True,
        )
        with patch.object(hub, "emit", new_callable=AsyncMock) as mock_emit:
            count = await mark_no_shows(session=async_session, hub=hub)

        assert count == 1
        mock_emit.assert_called_once_with(
            "appointment.no_show",
            {"booking_id": str(booking.id)},
        )


# ---------------------------------------------------------------------------
# Tests — Notification Hub Event Payload Contract
# ---------------------------------------------------------------------------


class TestNotificationEventPayloads:
    """Integration tests verifying event payload shape matches Hub contract.

    These test the NotificationHubClient directly to verify the JSON shape
    sent to the external hub API matches the expected contract.
    """

    async def test_booked_event_payload_has_required_fields(self):
        """appointment.booked payload: {event_type, data: {booking_id}}."""
        client = NotificationHubClient(
            url="http://hub.test", api_key="key", enabled=True,
        )
        with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock()

            await client.emit("appointment.booked", {"booking_id": "abc-123"})

            payload = mock_http.post.call_args[1]["json"]
            assert payload == {
                "event_type": "appointment.booked",
                "data": {"booking_id": "abc-123"},
            }

    async def test_cancelled_event_payload_has_required_fields(self):
        """appointment.cancelled payload: {event_type, data: {booking_id}}."""
        client = NotificationHubClient(
            url="http://hub.test", api_key="key", enabled=True,
        )
        with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock()

            await client.emit("appointment.cancelled", {"booking_id": "def-456"})

            payload = mock_http.post.call_args[1]["json"]
            assert payload == {
                "event_type": "appointment.cancelled",
                "data": {"booking_id": "def-456"},
            }

    async def test_no_show_event_payload_has_required_fields(self):
        """appointment.no_show payload: {event_type, data: {booking_id}}."""
        client = NotificationHubClient(
            url="http://hub.test", api_key="key", enabled=True,
        )
        with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock()

            await client.emit("appointment.no_show", {"booking_id": "ghi-789"})

            payload = mock_http.post.call_args[1]["json"]
            assert payload == {
                "event_type": "appointment.no_show",
                "data": {"booking_id": "ghi-789"},
            }

    async def test_all_events_include_api_key_header(self):
        """All event emissions include X-API-Key in headers."""
        client = NotificationHubClient(
            url="http://hub.test", api_key="secret-key", enabled=True,
        )
        for event_type in ["appointment.booked", "appointment.cancelled", "appointment.no_show"]:
            with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock()

                await client.emit(event_type, {"booking_id": "test"})

                headers = mock_http.post.call_args[1]["headers"]
                assert headers["X-API-Key"] == "secret-key", f"Missing key for {event_type}"

    async def test_event_posts_to_correct_endpoint(self):
        """All events POST to {hub_url}/api/events."""
        client = NotificationHubClient(
            url="http://my-hub.example.com", api_key="key", enabled=True,
        )
        with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock()

            await client.emit("appointment.booked", {"booking_id": "x"})

            url = mock_http.post.call_args[0][0]
            assert url == "http://my-hub.example.com/api/events"
