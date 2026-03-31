"""Booking API routes — create, list, get, cancel bookings.

Phase 4 implementation: POST /api/bookings (this batch).
GET and cancel endpoints will be added in subsequent batches.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import create_api_key_dependency
from src.api.schemas.booking_schemas import BookingCreate, BookingOut
from src.booking.service import create_booking
from src.config import get_settings
from src.db.session import get_session

logger = logging.getLogger(__name__)

settings = get_settings()
router = APIRouter(prefix="/api", tags=["bookings"])
_auth = create_api_key_dependency(settings.api_keys_list)


@router.post("/bookings", status_code=201)
async def create_booking_endpoint(
    body: BookingCreate,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> BookingOut:
    """Create a new booking or return existing if request_id matches."""
    booking, is_new = await create_booking(
        session=session,
        request_id=body.request_id,
        patient_name=body.patient_name,
        patient_email=body.patient_email,
        provider_id=body.provider_id,
        room_id=body.room_id,
        appointment_type_id=body.appointment_type_id,
        target_date=body.date,
        start_time=body.start_time,
    )

    if not is_new:
        response.status_code = 200

    return BookingOut.model_validate(booking)
