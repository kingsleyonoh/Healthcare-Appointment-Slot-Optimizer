"""Pydantic schemas for Booking API endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field


class BookingCreate(BaseModel):
    """Request body for POST /api/bookings."""

    request_id: str = Field(..., min_length=1)
    patient_name: str = Field(..., min_length=1)
    patient_email: str | None = None
    provider_id: uuid.UUID
    room_id: uuid.UUID
    appointment_type_id: uuid.UUID
    date: date
    start_time: time


class BookingOut(BaseModel):
    """Response schema for a single booking."""

    id: uuid.UUID
    request_id: str
    patient_name: str
    patient_email: str | None
    provider_id: uuid.UUID
    room_id: uuid.UUID
    appointment_type_id: uuid.UUID
    date: date
    start_time: time
    end_time: time
    status: str
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookingCancelRequest(BaseModel):
    """Request body for PUT /api/bookings/:id/cancel."""

    reason: str = Field(..., min_length=1)


class BookingCancelOut(BaseModel):
    """Response for cancellation — booking + backfill candidates."""

    booking: BookingOut
    backfill_candidates: list = Field(default_factory=list)
