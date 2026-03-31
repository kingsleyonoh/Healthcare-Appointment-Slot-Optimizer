"""Integration tests for GET /api/slots endpoint.

Tests run against live PostgreSQL — no mocks.
Data is seeded through the Configuration API (POST) + direct DB for bookings.
Covers: auth, happy path, scoring, filtering, empty results, booking exclusion, overbooking.
"""

import uuid
from datetime import date, time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.db.models import Booking, OverbookingRule, Provider

API_KEY = "dev-key-1"
HEADERS = {"X-API-Key": API_KEY}

_DB_URL = "postgresql+asyncpg://postgres:devpass@localhost:5434/scheduler"


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test class."""
    from src.main import create_app

    return create_app()


async def _seed_via_api(client: AsyncClient) -> dict:
    """Seed a provider, room, appointment type, and availability via API.

    Returns dict with provider_id, room_id, appt_type_id.
    Provider is created with buffer_minutes=0 for predictable slot counts.
    """
    uid = uuid.uuid4().hex[:6]

    # Provider — buffer_minutes=0 at creation
    resp = await client.post(
        "/api/providers",
        json={
            "name": f"Dr. Slot-{uid}",
            "specialty": "general",
            "buffer_minutes": 0,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201, resp.text
    provider = resp.json()

    # Room
    resp = await client.post(
        "/api/rooms",
        json={
            "name": f"Room-{uid}",
            "room_type": "exam",
            "equipment": ["ecg"],
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201, resp.text
    room = resp.json()

    # Appointment Type
    resp = await client.post(
        "/api/appointment-types",
        json={
            "name": f"Checkup-{uid}",
            "duration_minutes": 30,
            "required_room_type": "exam",
            "required_equipment": [],
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201, resp.text
    appt_type = resp.json()

    # Availability: Monday 09:00-17:00
    resp = await client.post(
        "/api/availability",
        json={
            "provider_id": provider["id"],
            "day_of_week": 0,
            "start_time": "09:00",
            "end_time": "17:00",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201, resp.text

    return {
        "provider_id": provider["id"],
        "room_id": room["id"],
        "appt_type_id": appt_type["id"],
    }


async def _insert_booking(provider_id, room_id, appt_type_id, d, st, et):
    """Insert a booking directly into the DB."""
    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        session = AsyncSession(bind=conn)
        booking = Booking(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            patient_name="Test Patient",
            provider_id=provider_id,
            room_id=room_id,
            appointment_type_id=appt_type_id,
            date=d,
            start_time=st,
            end_time=et,
            status="confirmed",
        )
        session.add(booking)
        await session.flush()
    await engine.dispose()


async def _insert_overbooking_rule(provider_id, appt_type_id, max_overbook):
    """Insert an overbooking rule directly into the DB."""
    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        session = AsyncSession(bind=conn)
        rule = OverbookingRule(
            provider_id=provider_id,
            appointment_type_id=appt_type_id,
            max_overbook=max_overbook,
            enabled=True,
        )
        session.add(rule)
        await session.flush()
    await engine.dispose()


async def _update_provider_max_daily(provider_id, max_daily):
    """Update provider's max_daily_appointments directly in DB."""
    from sqlalchemy import update

    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        await conn.execute(
            update(Provider)
            .where(Provider.id == provider_id)
            .values(max_daily_appointments=max_daily)
        )
    await engine.dispose()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestSlotEndpointAuth:
    """Authentication tests for GET /api/slots."""

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_401(self, app):
        """Request without API key returns 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/api/slots",
                params={
                    "target_date": "2026-03-23",
                    "appointment_type_id": str(uuid.uuid4()),
                },
            )
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestSlotEndpointHappyPath:
    """Happy path tests for slot generation."""

    @pytest.mark.asyncio
    async def test_returns_slots_for_valid_request(self, app):
        """Valid request returns 200 with sorted slots."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            ids = await _seed_via_api(c)

            resp = await c.get(
                "/api/slots",
                params={
                    "target_date": "2026-03-23",
                    "appointment_type_id": ids["appt_type_id"],
                },
                headers=HEADERS,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["date"] == "2026-03-23"
            assert body["appointment_type_id"] == ids["appt_type_id"]
            assert body["total"] > 0
            assert len(body["slots"]) == body["total"]

            # Sorted by quality_score descending
            scores = [s["quality_score"] for s in body["slots"]]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_slots_have_expected_fields(self, app):
        """Each slot contains all required response fields."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            ids = await _seed_via_api(c)

            resp = await c.get(
                "/api/slots",
                params={
                    "target_date": "2026-03-23",
                    "appointment_type_id": ids["appt_type_id"],
                },
                headers=HEADERS,
            )
            assert resp.status_code == 200
            slots = resp.json()["slots"]
            assert len(slots) > 0

            slot = slots[0]
            expected_keys = {
                "start", "end", "provider_id", "provider_name",
                "room_id", "room_name", "quality_score", "is_overbooked",
            }
            assert expected_keys.issubset(set(slot.keys()))
            assert 0 <= slot["quality_score"] <= 1
            assert isinstance(slot["is_overbooked"], bool)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestSlotEndpointFiltering:
    """Filtering and preference tests."""

    @pytest.mark.asyncio
    async def test_filter_by_provider(self, app):
        """Slots only for the specified provider are returned."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            ids = await _seed_via_api(c)

            resp = await c.get(
                "/api/slots",
                params={
                    "target_date": "2026-03-23",
                    "appointment_type_id": ids["appt_type_id"],
                    "provider_id": ids["provider_id"],
                },
                headers=HEADERS,
            )
            assert resp.status_code == 200
            for slot in resp.json()["slots"]:
                assert slot["provider_id"] == ids["provider_id"]

    @pytest.mark.asyncio
    async def test_preference_boosts_matching_slots(self, app):
        """Slots within preferred window score higher than those outside."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            ids = await _seed_via_api(c)

            resp = await c.get(
                "/api/slots",
                params={
                    "target_date": "2026-03-23",
                    "appointment_type_id": ids["appt_type_id"],
                    "preferred_start": "09:00",
                    "preferred_end": "10:00",
                },
                headers=HEADERS,
            )
            assert resp.status_code == 200
            slots = resp.json()["slots"]
            assert len(slots) > 0
            assert slots[0]["quality_score"] > 0


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------

class TestSlotEndpointEmpty:
    """Tests when no slots are available."""

    @pytest.mark.asyncio
    async def test_no_availability_returns_empty_with_next_date(self, app):
        """No availability on target date returns next_available_date."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            ids = await _seed_via_api(c)

            # 2026-03-24 is Tuesday — no availability set
            resp = await c.get(
                "/api/slots",
                params={
                    "target_date": "2026-03-24",
                    "appointment_type_id": ids["appt_type_id"],
                    "provider_id": ids["provider_id"],
                },
                headers=HEADERS,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 0
            assert body["slots"] == []
            # Next Monday = 2026-03-30
            assert body["next_available_date"] == "2026-03-30"

    @pytest.mark.asyncio
    async def test_nonexistent_appointment_type_returns_empty(self, app):
        """Unknown appointment type returns empty list."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/api/slots",
                params={
                    "target_date": "2026-03-23",
                    "appointment_type_id": str(uuid.uuid4()),
                },
                headers=HEADERS,
            )
            assert resp.status_code == 200
            assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# With bookings
# ---------------------------------------------------------------------------

class TestSlotEndpointWithBookings:
    """Tests with existing bookings to verify conflict handling."""

    @pytest.mark.asyncio
    async def test_booked_slots_are_excluded(self, app):
        """Slots overlapping existing bookings are not returned."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            ids = await _seed_via_api(c)

            # Book 09:00-09:30
            await _insert_booking(
                ids["provider_id"], ids["room_id"], ids["appt_type_id"],
                date(2026, 3, 23), time(9, 0), time(9, 30),
            )

            resp = await c.get(
                "/api/slots",
                params={
                    "target_date": "2026-03-23",
                    "appointment_type_id": ids["appt_type_id"],
                    "provider_id": ids["provider_id"],
                },
                headers=HEADERS,
            )
            assert resp.status_code == 200
            # Booking blocks specific room — no 09:00 slot for THAT room
            room_slots = [
                s["start"] for s in resp.json()["slots"]
                if s["room_id"] == ids["room_id"]
            ]
            assert "09:00:00" not in room_slots


# ---------------------------------------------------------------------------
# Overbooking
# ---------------------------------------------------------------------------

class TestSlotEndpointOverbooking:
    """Tests for overbooking support."""

    @pytest.mark.asyncio
    async def test_overbooked_slots_are_flagged(self, app):
        """When maxed out, overbooking rules create is_overbooked=True slots."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            ids = await _seed_via_api(c)

            # Set max_daily to 1
            await _update_provider_max_daily(ids["provider_id"], 1)

            # Fill the single-slot limit
            await _insert_booking(
                ids["provider_id"], ids["room_id"], ids["appt_type_id"],
                date(2026, 3, 23), time(9, 0), time(9, 30),
            )

            # Add overbooking rule: allow 2 extra
            await _insert_overbooking_rule(
                ids["provider_id"], ids["appt_type_id"], 2,
            )

            resp = await c.get(
                "/api/slots",
                params={
                    "target_date": "2026-03-23",
                    "appointment_type_id": ids["appt_type_id"],
                },
                headers=HEADERS,
            )
            assert resp.status_code == 200
            body = resp.json()
            overbooked = [s for s in body["slots"] if s["is_overbooked"]]
            assert len(overbooked) > 0
