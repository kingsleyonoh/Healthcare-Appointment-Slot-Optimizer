"""Configuration API CRUD routes.

Endpoints: providers, rooms, appointment-types, availability, overbooking-rules.
All protected by API-key auth; responses use the standard error envelope.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import create_api_key_dependency
from src.api.schemas.config_schemas import (
    AppointmentTypeCreate,
    AppointmentTypeOut,
    AvailabilityCreate,
    AvailabilityOut,
    OverbookingRuleCreate,
    OverbookingRuleOut,
    PaginatedResponse,
    ProviderCreate,
    ProviderOut,
    RoomCreate,
    RoomOut,
)
from src.config import get_settings
from src.db.models import (
    AppointmentType,
    OverbookingRule,
    Provider,
    ProviderAvailability,
    Room,
)
from src.db.session import get_session
from src.lib.errors import AppError
from src.lib.pagination import PaginationParams, get_pagination

logger = logging.getLogger(__name__)

settings = get_settings()
router = APIRouter(prefix="/api", tags=["configuration"])
_auth = create_api_key_dependency(settings.api_keys_list)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

@router.post("/providers", status_code=201)
async def create_provider(
    body: ProviderCreate,
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> ProviderOut:
    provider = Provider(**body.model_dump())
    session.add(provider)
    await session.flush()
    await session.refresh(provider)
    return ProviderOut.model_validate(provider)


@router.get("/providers")
async def list_providers(
    pagination: PaginationParams = Depends(get_pagination),
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> PaginatedResponse:
    total = (await session.execute(select(func.count(Provider.id)))).scalar_one()
    rows = (
        await session.execute(
            select(Provider)
            .order_by(Provider.created_at)
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()
    return PaginatedResponse(
        items=[ProviderOut.model_validate(r).model_dump(mode="json") for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

@router.post("/rooms", status_code=201)
async def create_room(
    body: RoomCreate,
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> RoomOut:
    room = Room(
        name=body.name,
        room_type=body.room_type.value,
        equipment=body.equipment,
        enabled=body.enabled,
    )
    session.add(room)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise AppError(
            code="CONFLICT",
            message=f"Room name '{body.name}' already exists",
            status_code=409,
        )
    await session.refresh(room)
    return RoomOut.model_validate(room)


@router.get("/rooms")
async def list_rooms(
    pagination: PaginationParams = Depends(get_pagination),
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> PaginatedResponse:
    total = (await session.execute(select(func.count(Room.id)))).scalar_one()
    rows = (
        await session.execute(
            select(Room)
            .order_by(Room.created_at)
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()
    return PaginatedResponse(
        items=[RoomOut.model_validate(r).model_dump(mode="json") for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


# ---------------------------------------------------------------------------
# Appointment Types
# ---------------------------------------------------------------------------

@router.post("/appointment-types", status_code=201)
async def create_appointment_type(
    body: AppointmentTypeCreate,
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> AppointmentTypeOut:
    appt = AppointmentType(
        name=body.name,
        duration_minutes=body.duration_minutes,
        required_room_type=body.required_room_type.value,
        required_equipment=body.required_equipment,
        color_code=body.color_code,
        enabled=body.enabled,
    )
    session.add(appt)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise AppError(
            code="CONFLICT",
            message=f"Appointment type '{body.name}' already exists",
            status_code=409,
        )
    await session.refresh(appt)
    return AppointmentTypeOut.model_validate(appt)


@router.get("/appointment-types")
async def list_appointment_types(
    pagination: PaginationParams = Depends(get_pagination),
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> PaginatedResponse:
    total = (
        await session.execute(select(func.count(AppointmentType.id)))
    ).scalar_one()
    rows = (
        await session.execute(
            select(AppointmentType)
            .order_by(AppointmentType.created_at)
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()
    return PaginatedResponse(
        items=[
            AppointmentTypeOut.model_validate(r).model_dump(mode="json") for r in rows
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


# ---------------------------------------------------------------------------
# Provider Availability
# ---------------------------------------------------------------------------

@router.post("/availability", status_code=201)
async def create_availability(
    body: AvailabilityCreate,
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> AvailabilityOut:
    # Check provider exists
    provider = await session.get(Provider, body.provider_id)
    if provider is None:
        raise AppError(
            code="NOT_FOUND",
            message=f"Provider {body.provider_id} not found",
            status_code=404,
        )
    avail = ProviderAvailability(
        provider_id=body.provider_id,
        day_of_week=body.day_of_week,
        start_time=body.start_time,
        end_time=body.end_time,
        **({"valid_from": body.valid_from} if body.valid_from else {}),
        **({"valid_until": body.valid_until} if body.valid_until else {}),
    )
    session.add(avail)
    await session.flush()
    await session.refresh(avail)
    return AvailabilityOut.model_validate(avail)


@router.get("/availability")
async def list_availability(
    provider_id: uuid.UUID | None = Query(None),
    pagination: PaginationParams = Depends(get_pagination),
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> PaginatedResponse:
    base = select(ProviderAvailability)
    count_q = select(func.count(ProviderAvailability.id))
    if provider_id:
        base = base.where(ProviderAvailability.provider_id == provider_id)
        count_q = count_q.where(ProviderAvailability.provider_id == provider_id)
    total = (await session.execute(count_q)).scalar_one()
    rows = (
        await session.execute(
            base.order_by(ProviderAvailability.created_at)
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()
    return PaginatedResponse(
        items=[
            AvailabilityOut.model_validate(r).model_dump(mode="json") for r in rows
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


# ---------------------------------------------------------------------------
# Overbooking Rules
# ---------------------------------------------------------------------------

@router.post("/overbooking-rules", status_code=201)
async def create_overbooking_rule(
    body: OverbookingRuleCreate,
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> OverbookingRuleOut:
    rule = OverbookingRule(**body.model_dump())
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return OverbookingRuleOut.model_validate(rule)


@router.get("/overbooking-rules")
async def list_overbooking_rules(
    provider_id: uuid.UUID | None = Query(None),
    pagination: PaginationParams = Depends(get_pagination),
    session: AsyncSession = Depends(get_session),
    _key: str = _auth,
) -> PaginatedResponse:
    base = select(OverbookingRule)
    count_q = select(func.count(OverbookingRule.id))
    if provider_id:
        base = base.where(OverbookingRule.provider_id == provider_id)
        count_q = count_q.where(OverbookingRule.provider_id == provider_id)
    total = (await session.execute(count_q)).scalar_one()
    rows = (
        await session.execute(
            base.order_by(OverbookingRule.created_at)
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()
    return PaginatedResponse(
        items=[
            OverbookingRuleOut.model_validate(r).model_dump(mode="json") for r in rows
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
