"""Pydantic schemas for the Schedule View API."""

from __future__ import annotations

import uuid
from datetime import date, time

from pydantic import BaseModel, Field


class ScheduleBooking(BaseModel):
    """Summary of a single booking in the schedule view."""

    id: uuid.UUID
    patient_name: str
    start_time: time
    end_time: time
    status: str
    appointment_type: str
    room_name: str


class ScheduleGap(BaseModel):
    """A gap between bookings within availability."""

    start_time: time
    end_time: time
    duration_minutes: int


class ProviderDaySchedule(BaseModel):
    """One provider's schedule for a single day."""

    date: date
    provider_id: str
    provider_name: str
    bookings: list[ScheduleBooking]
    gaps: list[ScheduleGap]
    utilization: float = Field(ge=0, le=1)


class ScheduleSummary(BaseModel):
    """Aggregate summary across all provider-days."""

    total_utilization: float


class ScheduleResponse(BaseModel):
    """Response body for GET /api/schedule."""

    schedule: list[ProviderDaySchedule]
    summary: ScheduleSummary
