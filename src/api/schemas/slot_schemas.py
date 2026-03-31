"""Pydantic schemas for the Slot Optimizer API."""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, Field


class SlotQuery(BaseModel):
    """Query parameters for GET /api/slots."""

    target_date: date = Field(..., description="Date to find slots for")
    appointment_type_id: str = Field(
        ..., description="UUID of the appointment type"
    )
    provider_id: str | None = Field(
        None, description="Optional provider filter"
    )
    preferred_start: time | None = Field(
        None, description="Start of patient preferred window"
    )
    preferred_end: time | None = Field(
        None, description="End of patient preferred window"
    )


class SlotOut(BaseModel):
    """Individual slot in the response."""

    start: str = Field(..., description="HH:MM:SS")
    end: str = Field(..., description="HH:MM:SS")
    provider_id: str
    provider_name: str
    room_id: str
    room_name: str
    quality_score: float = Field(
        ..., ge=0, le=1, description="Overall quality 0-1"
    )
    is_overbooked: bool


class SlotResponse(BaseModel):
    """Response body for GET /api/slots."""

    date: date
    appointment_type_id: str
    total: int
    slots: list[SlotOut]
    next_available_date: date | None = Field(
        None,
        description="Next date with availability if no slots found",
    )
