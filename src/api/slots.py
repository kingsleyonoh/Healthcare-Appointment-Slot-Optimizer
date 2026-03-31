"""Slot Optimizer API route — GET /api/slots.

Returns scored, sorted candidate appointment slots for a target date.
Protected by API-key auth.
"""

from __future__ import annotations

import logging
from datetime import date, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import create_api_key_dependency
from src.api.schemas.slot_schemas import SlotOut, SlotResponse
from src.config import get_settings
from src.db.session import get_session
from src.lib.errors import AppError
from src.optimizer.engine import find_available_slots, find_next_available_date

logger = logging.getLogger(__name__)

settings = get_settings()
verify_key = create_api_key_dependency(settings.api_keys_list)

router = APIRouter(prefix="/api", tags=["slots"])


@router.get(
    "/slots",
    response_model=SlotResponse,
    summary="Find available appointment slots",
)
async def get_slots(
    target_date: date = Query(..., description="Date to find slots for"),
    appointment_type_id: str = Query(
        ..., description="UUID of the appointment type"
    ),
    provider_id: str | None = Query(None, description="Filter by provider"),
    preferred_start: time | None = Query(
        None, description="Patient preferred window start (HH:MM)"
    ),
    preferred_end: time | None = Query(
        None, description="Patient preferred window end (HH:MM)"
    ),
    _key: str = verify_key,
    session: AsyncSession = Depends(get_session),
) -> SlotResponse:
    """Compute and return scored appointment slots.

    Returns empty slots list with ``next_available_date`` when no slots
    are found for the target date.
    """
    logger.info(
        "Slot query: date=%s type=%s provider=%s",
        target_date,
        appointment_type_id,
        provider_id,
    )

    raw_slots = await find_available_slots(
        session=session,
        target_date=target_date,
        appointment_type_id=appointment_type_id,
        provider_id=provider_id,
        preferred_start=preferred_start,
        preferred_end=preferred_end,
    )

    next_date = None
    if not raw_slots:
        next_date = await find_next_available_date(
            session=session,
            appointment_type_id=appointment_type_id,
            start_date=target_date,
        )

    return SlotResponse(
        date=target_date,
        appointment_type_id=appointment_type_id,
        total=len(raw_slots),
        slots=[SlotOut(**s) for s in raw_slots],
        next_available_date=next_date,
    )
