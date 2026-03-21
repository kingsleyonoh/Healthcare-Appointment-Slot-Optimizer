"""SQLAlchemy ORM models matching the PRD database schema.

All tables use UUID primary keys and ``server_default`` for timestamps
so the database generates values rather than the application.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all models."""

    pass


class Provider(Base):
    """Healthcare provider (doctor / clinician)."""

    __tablename__ = "providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    specialty: Mapped[str] = mapped_column(Text, nullable=False)
    max_daily_appointments: Mapped[int] = mapped_column(
        Integer, default=20, server_default=text("20"),
    )
    buffer_minutes: Mapped[int] = mapped_column(
        Integer, default=10, server_default=text("10"),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("now()"),
    )


class Room(Base):
    """Physical room where appointments take place."""

    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    room_type: Mapped[str] = mapped_column(Text, nullable=False)
    equipment: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'"),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("now()"),
    )


class AppointmentType(Base):
    """Category of appointment with duration and room requirements."""

    __tablename__ = "appointment_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    required_room_type: Mapped[str] = mapped_column(Text, nullable=False)
    required_equipment: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'"),
    )
    color_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("now()"),
    )


class ProviderAvailability(Base):
    """Recurring weekly availability window for a provider."""

    __tablename__ = "provider_availability"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    valid_from: Mapped[date] = mapped_column(
        Date, default=date(1970, 1, 1), server_default=text("'1970-01-01'"),
    )
    valid_until: Mapped[date] = mapped_column(
        Date, default=date(9999, 12, 31), server_default=text("'9999-12-31'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("now()"),
    )

    __table_args__ = (
        Index("ix_provider_availability_provider_dow", "provider_id", "day_of_week"),
    )


class Booking(Base):
    """Confirmed appointment booking."""

    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    request_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    patient_name: Mapped[str] = mapped_column(Text, nullable=False)
    patient_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointment_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="confirmed", server_default=text("'confirmed'"),
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("now()"),
    )

    __table_args__ = (
        UniqueConstraint("provider_id", "date", "start_time", name="uq_provider_slot"),
        UniqueConstraint("room_id", "date", "start_time", name="uq_room_slot"),
        Index("ix_bookings_date", "date"),
        Index("ix_bookings_status", "status"),
        Index("ix_bookings_provider_date", "provider_id", "date"),
    )


class OverbookingRule(Base):
    """Optional rule allowing controlled overbooking."""

    __tablename__ = "overbooking_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=True,
    )
    appointment_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointment_types.id", ondelete="CASCADE"),
        nullable=True,
    )
    max_overbook: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("now()"),
    )

    __table_args__ = (
        Index("ix_overbooking_provider_appt", "provider_id", "appointment_type_id"),
    )
