"""Integration tests for bookings API — create, list, get, cancel."""

from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app


def _next_weekday(dow: int = 0) -> date:
    today = date.today()
    days_ahead = dow - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


API_KEY = "dev-key-1"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed_via_api(client) -> dict:
    """Create prerequisite data via the real API endpoints."""
    # Provider
    resp = await client.post(
        "/api/providers",
        json={"name": "Dr. Booking Test", "specialty": "General"},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    provider = resp.json()

    # Room
    resp = await client.post(
        "/api/rooms",
        json={"name": "Booking Room", "room_type": "consultation"},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    room = resp.json()

    # Appointment type
    resp = await client.post(
        "/api/appointment-types",
        json={
            "name": "Booking Checkup",
            "duration_minutes": 30,
            "required_room_type": "consultation",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    appt_type = resp.json()

    # Availability — Monday 08:00-17:00
    resp = await client.post(
        "/api/availability",
        json={
            "provider_id": provider["id"],
            "day_of_week": 0,
            "start_time": "08:00",
            "end_time": "17:00",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201

    return {"provider": provider, "room": room, "appt_type": appt_type}


class TestCreateBookingEndpoint:
    """POST /api/bookings integration tests."""

    async def test_create_booking_returns_201(self, client):
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        resp = await client.post(
            "/api/bookings",
            json={
                "request_id": "api-001",
                "patient_name": "Alice",
                "provider_id": data["provider"]["id"],
                "room_id": data["room"]["id"],
                "appointment_type_id": data["appt_type"]["id"],
                "date": target,
                "start_time": "09:00",
            },
            headers=HEADERS,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["request_id"] == "api-001"
        assert body["status"] == "confirmed"
        assert body["end_time"] == "09:30:00"

    async def test_no_auth_returns_401(self, client):
        resp = await client.post(
            "/api/bookings",
            json={
                "request_id": "api-noauth",
                "patient_name": "Bob",
                "provider_id": "00000000-0000-0000-0000-000000000001",
                "room_id": "00000000-0000-0000-0000-000000000002",
                "appointment_type_id": "00000000-0000-0000-0000-000000000003",
                "date": _next_weekday(0).isoformat(),
                "start_time": "09:00",
            },
        )
        assert resp.status_code == 401

    async def test_missing_required_field_returns_422(self, client):
        resp = await client.post(
            "/api/bookings",
            json={"request_id": "api-missing"},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    async def test_duplicate_request_id_returns_same_booking(self, client):
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()
        payload = {
            "request_id": "api-dup",
            "patient_name": "Carol",
            "provider_id": data["provider"]["id"],
            "room_id": data["room"]["id"],
            "appointment_type_id": data["appt_type"]["id"],
            "date": target,
            "start_time": "10:00",
        }

        first = await client.post("/api/bookings", json=payload, headers=HEADERS)
        second = await client.post("/api/bookings", json=payload, headers=HEADERS)

        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]

    async def test_outside_availability_returns_error(self, client):
        data = await _seed_via_api(client)
        # Tuesday — provider only has Monday availability
        target_tue = _next_weekday(1).isoformat()

        resp = await client.post(
            "/api/bookings",
            json={
                "request_id": "api-no-avail",
                "patient_name": "Dan",
                "provider_id": data["provider"]["id"],
                "room_id": data["room"]["id"],
                "appointment_type_id": data["appt_type"]["id"],
                "date": target_tue,
                "start_time": "09:00",
            },
            headers=HEADERS,
        )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# GET /api/bookings — list with filters
# ---------------------------------------------------------------------------


class TestListBookingsEndpoint:
    """GET /api/bookings integration tests."""

    async def test_list_bookings_returns_paginated(self, client):
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        # Create 2 bookings
        for i in range(2):
            await client.post(
                "/api/bookings",
                json={
                    "request_id": f"api-list-{i}",
                    "patient_name": f"ListPatient{i}",
                    "provider_id": data["provider"]["id"],
                    "room_id": data["room"]["id"],
                    "appointment_type_id": data["appt_type"]["id"],
                    "date": target,
                    "start_time": f"{9 + i:02d}:00",
                },
                headers=HEADERS,
            )

        resp = await client.get("/api/bookings", headers=HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] >= 2
        assert len(body["items"]) >= 2

    async def test_list_bookings_filters_by_status(self, client):
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        await client.post(
            "/api/bookings",
            json={
                "request_id": "api-list-filt",
                "patient_name": "FilterPatient",
                "provider_id": data["provider"]["id"],
                "room_id": data["room"]["id"],
                "appointment_type_id": data["appt_type"]["id"],
                "date": target,
                "start_time": "09:00",
            },
            headers=HEADERS,
        )

        confirmed = await client.get(
            "/api/bookings", params={"status": "confirmed"}, headers=HEADERS
        )
        cancelled = await client.get(
            "/api/bookings", params={"status": "cancelled"}, headers=HEADERS
        )

        assert confirmed.status_code == 200
        assert confirmed.json()["total"] >= 1
        # No cancelled bookings yet
        assert cancelled.json()["total"] == 0

    async def test_list_bookings_no_auth_returns_401(self, client):
        resp = await client.get("/api/bookings")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/bookings/:id — single booking
# ---------------------------------------------------------------------------


class TestGetBookingEndpoint:
    """GET /api/bookings/:id integration tests."""

    async def test_get_booking_returns_details(self, client):
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        create_resp = await client.post(
            "/api/bookings",
            json={
                "request_id": "api-get-1",
                "patient_name": "GetPatient",
                "provider_id": data["provider"]["id"],
                "room_id": data["room"]["id"],
                "appointment_type_id": data["appt_type"]["id"],
                "date": target,
                "start_time": "09:00",
            },
            headers=HEADERS,
        )
        booking_id = create_resp.json()["id"]

        resp = await client.get(f"/api/bookings/{booking_id}", headers=HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == booking_id
        assert body["patient_name"] == "GetPatient"
        assert body["status"] == "confirmed"

    async def test_get_nonexistent_booking_returns_404(self, client):
        fake_id = "00000000-0000-0000-0000-000000000099"
        resp = await client.get(f"/api/bookings/{fake_id}", headers=HEADERS)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# PUT /api/bookings/:id/cancel
# ---------------------------------------------------------------------------


class TestCancelBookingEndpoint:
    """PUT /api/bookings/:id/cancel integration tests."""

    async def test_cancel_booking_returns_cancelled_state(self, client):
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        create_resp = await client.post(
            "/api/bookings",
            json={
                "request_id": "api-cancel-1",
                "patient_name": "CancelPatient",
                "provider_id": data["provider"]["id"],
                "room_id": data["room"]["id"],
                "appointment_type_id": data["appt_type"]["id"],
                "date": target,
                "start_time": "09:00",
            },
            headers=HEADERS,
        )
        booking_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/bookings/{booking_id}/cancel",
            json={"reason": "No longer needed"},
            headers=HEADERS,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["booking"]["status"] == "cancelled"
        assert body["booking"]["cancellation_reason"] == "No longer needed"
        assert "backfill_candidates" in body

    async def test_cancel_idempotent_returns_same_state(self, client):
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        create_resp = await client.post(
            "/api/bookings",
            json={
                "request_id": "api-cancel-idem",
                "patient_name": "IdemPatient",
                "provider_id": data["provider"]["id"],
                "room_id": data["room"]["id"],
                "appointment_type_id": data["appt_type"]["id"],
                "date": target,
                "start_time": "10:00",
            },
            headers=HEADERS,
        )
        booking_id = create_resp.json()["id"]

        first = await client.put(
            f"/api/bookings/{booking_id}/cancel",
            json={"reason": "First"},
            headers=HEADERS,
        )
        second = await client.put(
            f"/api/bookings/{booking_id}/cancel",
            json={"reason": "Second"},
            headers=HEADERS,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["booking"]["cancellation_reason"] == "First"

    async def test_cancel_nonexistent_returns_404(self, client):
        fake_id = "00000000-0000-0000-0000-000000000099"
        resp = await client.put(
            f"/api/bookings/{fake_id}/cancel",
            json={"reason": "N/A"},
            headers=HEADERS,
        )
        assert resp.status_code == 404
