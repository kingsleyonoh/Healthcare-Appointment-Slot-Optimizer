"""Pydantic schemas for Configuration API endpoints.

Covers: Providers, Rooms, Appointment Types, Provider Availability,
and Overbooking Rules.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from enum import Enum

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RoomType(str, Enum):
    """Allowed room types."""
    exam = "exam"
    general = "general"
    procedure = "procedure"
    lab = "lab"
    consultation = "consultation"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    """Generic paginated list response."""
    items: list
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class ProviderCreate(BaseModel):
    name: str
    specialty: str
    max_daily_appointments: int = 20
    buffer_minutes: int = 10
    enabled: bool = True


class ProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    specialty: str
    max_daily_appointments: int
    buffer_minutes: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------

class RoomCreate(BaseModel):
    name: str
    room_type: RoomType
    equipment: list[str] = Field(default_factory=list)
    enabled: bool = True


class RoomOut(BaseModel):
    id: uuid.UUID
    name: str
    room_type: str
    equipment: list[str]
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Appointment Type
# ---------------------------------------------------------------------------

class AppointmentTypeCreate(BaseModel):
    name: str
    duration_minutes: int
    required_room_type: RoomType
    required_equipment: list[str] = Field(default_factory=list)
    color_code: str | None = None
    enabled: bool = True


class AppointmentTypeOut(BaseModel):
    id: uuid.UUID
    name: str
    duration_minutes: int
    required_room_type: str
    required_equipment: list[str]
    color_code: str | None
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Provider Availability
# ---------------------------------------------------------------------------

class AvailabilityCreate(BaseModel):
    provider_id: uuid.UUID
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    valid_from: date | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def _end_after_start(self) -> "AvailabilityCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilityOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    day_of_week: int
    start_time: time
    end_time: time
    valid_from: date
    valid_until: date
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Overbooking Rule
# ---------------------------------------------------------------------------

class OverbookingRuleCreate(BaseModel):
    provider_id: uuid.UUID | None = None
    appointment_type_id: uuid.UUID | None = None
    max_overbook: int
    enabled: bool = True


class OverbookingRuleOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID | None
    appointment_type_id: uuid.UUID | None
    max_overbook: int
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
