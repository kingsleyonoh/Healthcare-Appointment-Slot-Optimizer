"""Integration tests for src.db.models — SQLAlchemy model definitions."""

import uuid
from datetime import date, datetime, time

import pytest
from sqlalchemy import select


class TestProviderModel:
    """Test the Provider ORM model."""

    async def test_create_provider(self, async_session):
        """Should insert a Provider row with all required fields."""
        from src.db.models import Provider

        provider = Provider(
            name="Dr. Smith",
            specialty="cardiology",
        )
        async_session.add(provider)
        await async_session.flush()

        assert provider.id is not None
        assert provider.name == "Dr. Smith"
        assert provider.specialty == "cardiology"
        assert provider.max_daily_appointments == 20
        assert provider.buffer_minutes == 10
        assert provider.enabled is True

    async def test_provider_uuid_auto_generated(self, async_session):
        """Provider.id should be a UUID generated automatically."""
        from src.db.models import Provider

        p = Provider(name="Dr. Jones", specialty="general")
        async_session.add(p)
        await async_session.flush()
        assert isinstance(p.id, uuid.UUID)


class TestRoomModel:
    """Test the Room ORM model."""

    async def test_create_room(self, async_session):
        """Should insert a Room with required fields and defaults."""
        from src.db.models import Room

        room = Room(name="Room A", room_type="consultation")
        async_session.add(room)
        await async_session.flush()

        assert room.id is not None
        assert room.name == "Room A"
        assert room.room_type == "consultation"
        assert room.equipment == []
        assert room.enabled is True

    async def test_room_with_equipment(self, async_session):
        """Room should accept an equipment array."""
        from src.db.models import Room

        room = Room(
            name="Surgery B",
            room_type="procedure",
            equipment=["scalpel", "monitor"],
        )
        async_session.add(room)
        await async_session.flush()
        assert room.equipment == ["scalpel", "monitor"]


class TestAppointmentTypeModel:
    """Test the AppointmentType ORM model."""

    async def test_create_appointment_type(self, async_session):
        """Should insert an AppointmentType with duration and room type."""
        from src.db.models import AppointmentType

        apt = AppointmentType(
            name="Check-up",
            duration_minutes=30,
            required_room_type="consultation",
        )
        async_session.add(apt)
        await async_session.flush()

        assert apt.id is not None
        assert apt.duration_minutes == 30
        assert apt.required_room_type == "consultation"
        assert apt.enabled is True


class TestProviderAvailabilityModel:
    """Test the ProviderAvailability model with FK to providers."""

    async def test_create_availability(self, async_session):
        """Should create an availability window linked to a provider."""
        from src.db.models import Provider, ProviderAvailability

        provider = Provider(name="Dr. Lee", specialty="dermatology")
        async_session.add(provider)
        await async_session.flush()

        avail = ProviderAvailability(
            provider_id=provider.id,
            day_of_week=0,  # Monday
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        async_session.add(avail)
        await async_session.flush()

        assert avail.id is not None
        assert avail.provider_id == provider.id
        assert avail.day_of_week == 0


class TestBookingModel:
    """Test the Booking ORM model."""

    async def test_create_booking(self, async_session):
        """Should create a booking with all required fields."""
        from src.db.models import (
            AppointmentType,
            Booking,
            Provider,
            Room,
        )

        provider = Provider(name="Dr. Ada", specialty="neurology")
        room = Room(name="Room 1", room_type="consultation")
        appt = AppointmentType(
            name="Consultation",
            duration_minutes=30,
            required_room_type="consultation",
        )
        async_session.add_all([provider, room, appt])
        await async_session.flush()

        booking = Booking(
            request_id="req-001",
            patient_name="Jane Doe",
            provider_id=provider.id,
            room_id=room.id,
            appointment_type_id=appt.id,
            date=date(2026, 4, 1),
            start_time=time(10, 0),
            end_time=time(10, 30),
        )
        async_session.add(booking)
        await async_session.flush()

        assert booking.id is not None
        assert booking.status == "confirmed"
        assert booking.request_id == "req-001"


class TestOverbookingRuleModel:
    """Test the OverbookingRule ORM model."""

    async def test_create_global_rule(self, async_session):
        """A rule without provider_id should apply globally."""
        from src.db.models import OverbookingRule

        rule = OverbookingRule(max_overbook=2)
        async_session.add(rule)
        await async_session.flush()

        assert rule.id is not None
        assert rule.provider_id is None
        assert rule.max_overbook == 2
        assert rule.enabled is True
