"""Integration tests for Configuration API CRUD endpoints.

Tests run against live PostgreSQL — no mocks.
Covers: happy path, validation errors, UNIQUE conflicts, pagination, enum, auth.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

API_KEY = "dev-key-1"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test class."""
    from src.main import create_app

    return create_app()


# ---------------------------------------------------------------------------
# Provider CRUD
# ---------------------------------------------------------------------------

class TestProviderCreate:
    """POST /api/providers"""

    @pytest.mark.asyncio
    async def test_create_provider_success(self, app):
        """Creating a provider with valid data returns 201."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/providers",
                json={"name": "Dr. Alice", "specialty": "cardiology"},
                headers=HEADERS,
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["name"] == "Dr. Alice"
            assert body["specialty"] == "cardiology"
            assert "id" in body
            assert body["max_daily_appointments"] == 20  # default
            assert body["buffer_minutes"] == 10  # default
            assert body["enabled"] is True

    @pytest.mark.asyncio
    async def test_create_provider_missing_name_returns_422(self, app):
        """Missing required field 'name' returns 422 validation error."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/providers",
                json={"specialty": "cardiology"},
                headers=HEADERS,
            )
            assert resp.status_code == 422
            body = resp.json()
            assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_create_provider_no_auth_returns_401(self, app):
        """Missing API key returns 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/providers",
                json={"name": "Dr. Bob", "specialty": "dermatology"},
            )
            assert resp.status_code == 401


class TestProviderList:
    """GET /api/providers"""

    @pytest.mark.asyncio
    async def test_list_providers_returns_paginated(self, app):
        """Listing providers returns paginated response with items array."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # Create a provider first
            await c.post(
                "/api/providers",
                json={"name": "Dr. List Test", "specialty": "neurology"},
                headers=HEADERS,
            )
            resp = await c.get("/api/providers", headers=HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert "items" in body
            assert "total" in body
            assert "page" in body
            assert "page_size" in body

    @pytest.mark.asyncio
    async def test_list_providers_pagination_params(self, app):
        """Custom page_size limits results."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/api/providers",
                params={"page": 1, "page_size": 2},
                headers=HEADERS,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["page_size"] <= 2

    @pytest.mark.asyncio
    async def test_list_providers_max_page_size_capped(self, app):
        """page_size over 100 is capped to 100."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/api/providers",
                params={"page_size": 500},
                headers=HEADERS,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["page_size"] <= 100


# ---------------------------------------------------------------------------
# Room CRUD
# ---------------------------------------------------------------------------

class TestRoomCreate:
    """POST /api/rooms"""

    @pytest.mark.asyncio
    async def test_create_room_success(self, app):
        """Creating a room with valid data returns 201."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            unique_name = f"Room-{uuid.uuid4().hex[:8]}"
            resp = await c.post(
                "/api/rooms",
                json={"name": unique_name, "room_type": "exam"},
                headers=HEADERS,
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["name"] == unique_name
            assert body["room_type"] == "exam"
            assert body["equipment"] == []
            assert body["enabled"] is True

    @pytest.mark.asyncio
    async def test_create_room_invalid_room_type_returns_422(self, app):
        """Invalid room_type enum value returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/rooms",
                json={"name": "Bad Room", "room_type": "nonexistent_type"},
                headers=HEADERS,
            )
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_room_duplicate_name_returns_409(self, app):
        """Duplicate room name returns 409 conflict."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            name = f"DupRoom-{uuid.uuid4().hex[:8]}"
            await c.post(
                "/api/rooms",
                json={"name": name, "room_type": "general"},
                headers=HEADERS,
            )
            resp = await c.post(
                "/api/rooms",
                json={"name": name, "room_type": "exam"},
                headers=HEADERS,
            )
            assert resp.status_code == 409
            body = resp.json()
            assert body["error"]["code"] == "CONFLICT"


class TestRoomList:
    """GET /api/rooms"""

    @pytest.mark.asyncio
    async def test_list_rooms_returns_200(self, app):
        """Listing rooms returns 200 with items array."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/rooms", headers=HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert "items" in body


# ---------------------------------------------------------------------------
# Appointment Type CRUD
# ---------------------------------------------------------------------------

class TestAppointmentTypeCreate:
    """POST /api/appointment-types"""

    @pytest.mark.asyncio
    async def test_create_appointment_type_success(self, app):
        """Creating an appointment type returns 201."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            unique_name = f"Checkup-{uuid.uuid4().hex[:8]}"
            resp = await c.post(
                "/api/appointment-types",
                json={
                    "name": unique_name,
                    "duration_minutes": 30,
                    "required_room_type": "exam",
                },
                headers=HEADERS,
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["name"] == unique_name
            assert body["duration_minutes"] == 30
            assert body["required_room_type"] == "exam"

    @pytest.mark.asyncio
    async def test_create_appointment_type_duplicate_name_returns_409(self, app):
        """Duplicate appointment type name returns 409."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            name = f"DupType-{uuid.uuid4().hex[:8]}"
            await c.post(
                "/api/appointment-types",
                json={"name": name, "duration_minutes": 15, "required_room_type": "general"},
                headers=HEADERS,
            )
            resp = await c.post(
                "/api/appointment-types",
                json={"name": name, "duration_minutes": 30, "required_room_type": "exam"},
                headers=HEADERS,
            )
            assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_appointment_type_missing_duration_returns_422(self, app):
        """Missing required field returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/appointment-types",
                json={"name": "Incomplete"},
                headers=HEADERS,
            )
            assert resp.status_code == 422


class TestAppointmentTypeList:
    """GET /api/appointment-types"""

    @pytest.mark.asyncio
    async def test_list_appointment_types_returns_200(self, app):
        """Listing appointment types returns 200."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/appointment-types", headers=HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert "items" in body


# ---------------------------------------------------------------------------
# Provider Availability CRUD
# ---------------------------------------------------------------------------

class TestAvailabilityCreate:
    """POST /api/availability"""

    @pytest.mark.asyncio
    async def test_create_availability_success(self, app):
        """Creating availability for a valid provider returns 201."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # Create provider first
            prov = await c.post(
                "/api/providers",
                json={"name": "Dr. Avail", "specialty": "orthopedics"},
                headers=HEADERS,
            )
            provider_id = prov.json()["id"]
            resp = await c.post(
                "/api/availability",
                json={
                    "provider_id": provider_id,
                    "day_of_week": 1,
                    "start_time": "08:00",
                    "end_time": "17:00",
                },
                headers=HEADERS,
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["provider_id"] == provider_id
            assert body["day_of_week"] == 1

    @pytest.mark.asyncio
    async def test_create_availability_invalid_provider_returns_error(self, app):
        """Non-existent provider_id returns error."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            fake_id = str(uuid.uuid4())
            resp = await c.post(
                "/api/availability",
                json={
                    "provider_id": fake_id,
                    "day_of_week": 1,
                    "start_time": "08:00",
                    "end_time": "17:00",
                },
                headers=HEADERS,
            )
            # Should be 404 or 422 — provider doesn't exist
            assert resp.status_code in (404, 422)

    @pytest.mark.asyncio
    async def test_create_availability_end_before_start_returns_422(self, app):
        """end_time before start_time returns validation error."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            prov = await c.post(
                "/api/providers",
                json={"name": "Dr. TimeFlip", "specialty": "radiology"},
                headers=HEADERS,
            )
            provider_id = prov.json()["id"]
            resp = await c.post(
                "/api/availability",
                json={
                    "provider_id": provider_id,
                    "day_of_week": 3,
                    "start_time": "17:00",
                    "end_time": "08:00",
                },
                headers=HEADERS,
            )
            assert resp.status_code == 422


class TestAvailabilityList:
    """GET /api/availability"""

    @pytest.mark.asyncio
    async def test_list_availability_filtered_by_provider(self, app):
        """Listing availability with provider_id filter returns 200."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # Create provider + availability
            prov = await c.post(
                "/api/providers",
                json={"name": "Dr. FilterAvail", "specialty": "oncology"},
                headers=HEADERS,
            )
            provider_id = prov.json()["id"]
            await c.post(
                "/api/availability",
                json={
                    "provider_id": provider_id,
                    "day_of_week": 0,
                    "start_time": "09:00",
                    "end_time": "12:00",
                },
                headers=HEADERS,
            )
            resp = await c.get(
                "/api/availability",
                params={"provider_id": provider_id},
                headers=HEADERS,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert "items" in body


# ---------------------------------------------------------------------------
# Overbooking Rules CRUD
# ---------------------------------------------------------------------------

class TestOverbookingRuleCreate:
    """POST /api/overbooking-rules"""

    @pytest.mark.asyncio
    async def test_create_global_overbooking_rule(self, app):
        """Creating a global overbooking rule (no provider) returns 201."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/overbooking-rules",
                json={"max_overbook": 2},
                headers=HEADERS,
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["max_overbook"] == 2
            assert body["provider_id"] is None

    @pytest.mark.asyncio
    async def test_create_provider_specific_overbooking_rule(self, app):
        """Creating a provider-specific overbooking rule returns 201."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            prov = await c.post(
                "/api/providers",
                json={"name": "Dr. Overbook", "specialty": "pediatrics"},
                headers=HEADERS,
            )
            provider_id = prov.json()["id"]
            resp = await c.post(
                "/api/overbooking-rules",
                json={"provider_id": provider_id, "max_overbook": 1},
                headers=HEADERS,
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["provider_id"] == provider_id

    @pytest.mark.asyncio
    async def test_create_overbooking_rule_missing_max_returns_422(self, app):
        """Missing max_overbook returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/overbooking-rules",
                json={},
                headers=HEADERS,
            )
            assert resp.status_code == 422


class TestOverbookingRuleList:
    """GET /api/overbooking-rules"""

    @pytest.mark.asyncio
    async def test_list_overbooking_rules_returns_200(self, app):
        """Listing overbooking rules returns 200."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/overbooking-rules", headers=HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert "items" in body

    @pytest.mark.asyncio
    async def test_list_overbooking_rules_with_provider_filter(self, app):
        """Filtering by provider_id returns 200."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/api/overbooking-rules",
                params={"provider_id": str(uuid.uuid4())},
                headers=HEADERS,
            )
            assert resp.status_code == 200
