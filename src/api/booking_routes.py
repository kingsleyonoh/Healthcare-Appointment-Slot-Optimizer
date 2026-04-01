"""Booking API routes — create, list, get, cancel bookings."""

from __future__ import annotations

import logging
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import create_api_key_dependency
from src.api.schemas.booking_schemas import (
    BackfillCandidateOut,
    BookingCancelOut,
    BookingCancelRequest,
    BookingCreate,
    BookingOut,
)
from src.api.schemas.config_schemas import PaginatedResponse
from src.booking.backfill import find_backfill_candidates
from src.booking.service import cancel_booking, create_booking, get_booking, list_bookings
from src.config import get_settings
from src.db.session import get_session
from src.integrations.notification_hub import NotificationHubClient
from src.lib.pagination import PaginationParams, get_pagination

logger = logging.getLogger(__name__)

settings = get_settings()
router = APIRouter(prefix="/api", tags=["bookings"])
_auth = create_api_key_dependency(settings.api_keys_list)
_hub = NotificationHubClient(
    url=settings.NOTIFICATION_HUB_URL,
    api_key=settings.NOTIFICATION_HUB_API_KEY,
    enabled=settings.NOTIFICATION_HUB_ENABLED,
)


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

    if is_new:
        await _hub.emit("appointment.booked", {"booking_id": str(booking.id)})

    return BookingOut.model_validate(booking)


@router.get("/bookings")
async def list_bookings_endpoint(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    provider_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    pagination: PaginationParams = Depends(get_pagination),
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> PaginatedResponse:
    """List bookings with optional filters and pagination."""
    rows, total = await list_bookings(
        session=session,
        pagination=pagination,
        date_from=date_from,
        date_to=date_to,
        provider_id=provider_id,
        status=status,
    )
    return PaginatedResponse(
        items=[BookingOut.model_validate(r).model_dump(mode="json") for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/bookings/{booking_id}")
async def get_booking_endpoint(
    booking_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> BookingOut:
    """Get a single booking by ID."""
    booking = await get_booking(session=session, booking_id=booking_id)
    return BookingOut.model_validate(booking)


@router.put("/bookings/{booking_id}/cancel")
async def cancel_booking_endpoint(
    booking_id: uuid.UUID,
    body: BookingCancelRequest,
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> BookingCancelOut:
    """Cancel a booking. Idempotent for already-cancelled bookings."""
    booking = await cancel_booking(
        session=session, booking_id=booking_id, reason=body.reason
    )
    await _hub.emit("appointment.cancelled", {"booking_id": str(booking.id)})
    candidates = await find_backfill_candidates(
        session=session, cancelled_booking=booking,
    )
    return BookingCancelOut(
        booking=BookingOut.model_validate(booking),
        backfill_candidates=[BackfillCandidateOut(**c) for c in candidates],
    )
