"""Integration tests for GET /api/schedule endpoint.

Tests run against live PostgreSQL — no mocks.
Covers: auth, happy path, empty schedule, invalid date range, provider filter.
"""

from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app

API_KEY = "dev-key-1"
HEADERS = {"X-API-Key": API_KEY}


def _next_weekday(dow: int = 0) -> date:
    today = date.today()
    days_ahead = dow - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed_via_api(client) -> dict:
    """Create provider, room, appointment type, and availability."""
    resp = await client.post(
        "/api/providers",
        json={"name": "Dr. Schedule", "specialty": "General", "buffer_minutes": 0},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    provider = resp.json()

    resp = await client.post(
        "/api/rooms",
        json={"name": "Schedule Room", "room_type": "consultation"},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    room = resp.json()

    resp = await client.post(
        "/api/appointment-types",
        json={
            "name": "Schedule Checkup",
            "duration_minutes": 30,
            "required_room_type": "consultation",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    appt_type = resp.json()

    # Availability: Monday 08:00-17:00
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


class TestScheduleAuth:
    """Authentication tests for GET /api/schedule."""

    async def test_no_auth_returns_401(self, client):
        target = _next_weekday(0).isoformat()
        resp = await client.get(
            "/api/schedule",
            params={"date_from": target, "date_to": target},
        )
        assert resp.status_code == 401


class TestScheduleHappyPath:
    """Happy path tests for schedule view."""

    async def test_returns_schedule_with_bookings(self, client):
        """Schedule with bookings returns utilization > 0."""
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        # Create a booking
        await client.post(
            "/api/bookings",
            json={
                "request_id": "sched-1",
                "patient_name": "Alice",
                "provider_id": data["provider"]["id"],
                "room_id": data["room"]["id"],
                "appointment_type_id": data["appt_type"]["id"],
                "date": target,
                "start_time": "09:00",
            },
            headers=HEADERS,
        )

        resp = await client.get(
            "/api/schedule",
            params={"date_from": target, "date_to": target},
            headers=HEADERS,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "schedule" in body
        assert "summary" in body
        assert len(body["schedule"]) >= 1

        day = body["schedule"][0]
        assert day["date"] == target
        assert day["provider_id"] == data["provider"]["id"]
        assert len(day["bookings"]) >= 1
        assert day["utilization"] > 0

    async def test_schedule_includes_gaps(self, client):
        """Schedule highlights gaps between bookings."""
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        # Book at 09:00 and 11:00 — gap at 09:30-11:00
        for req_id, hour in [("sched-gap-1", "09:00"), ("sched-gap-2", "11:00")]:
            await client.post(
                "/api/bookings",
                json={
                    "request_id": req_id,
                    "patient_name": "GapPatient",
                    "provider_id": data["provider"]["id"],
                    "room_id": data["room"]["id"],
                    "appointment_type_id": data["appt_type"]["id"],
                    "date": target,
                    "start_time": hour,
                },
                headers=HEADERS,
            )

        resp = await client.get(
            "/api/schedule",
            params={"date_from": target, "date_to": target},
            headers=HEADERS,
        )

        assert resp.status_code == 200
        day = resp.json()["schedule"][0]
        assert len(day["gaps"]) >= 1
        gap = day["gaps"][0]
        assert "start_time" in gap
        assert "end_time" in gap
        assert "duration_minutes" in gap

    async def test_summary_contains_total_utilization(self, client):
        """Summary includes total_utilization across all provider-days."""
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        resp = await client.get(
            "/api/schedule",
            params={"date_from": target, "date_to": target},
            headers=HEADERS,
        )

        assert resp.status_code == 200
        summary = resp.json()["summary"]
        assert "total_utilization" in summary
        assert isinstance(summary["total_utilization"], float)


class TestScheduleEmpty:
    """Tests for empty schedule scenarios."""

    async def test_no_bookings_returns_zero_utilization(self, client):
        """Date range with no bookings returns 0% utilization."""
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        resp = await client.get(
            "/api/schedule",
            params={"date_from": target, "date_to": target},
            headers=HEADERS,
        )

        assert resp.status_code == 200
        body = resp.json()
        # Provider has availability on Monday but no bookings
        day = body["schedule"][0]
        assert day["utilization"] == 0.0
        assert day["bookings"] == []

    async def test_no_availability_returns_empty_schedule(self, client):
        """Date with no provider availability returns empty schedule."""
        await _seed_via_api(client)
        # Tuesday — provider only has Monday availability
        target = _next_weekday(1).isoformat()

        resp = await client.get(
            "/api/schedule",
            params={"date_from": target, "date_to": target},
            headers=HEADERS,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["schedule"] == []
        assert body["summary"]["total_utilization"] == 0.0


class TestScheduleValidation:
    """Validation and error handling tests."""

    async def test_invalid_date_range_returns_400(self, client):
        """date_to before date_from returns 400."""
        resp = await client.get(
            "/api/schedule",
            params={"date_from": "2026-04-10", "date_to": "2026-04-05"},
            headers=HEADERS,
        )
        assert resp.status_code == 400


class TestScheduleFiltering:
    """Filter tests for schedule view."""

    async def test_filter_by_provider_id(self, client):
        """Only the specified provider's schedule is returned."""
        data = await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        resp = await client.get(
            "/api/schedule",
            params={
                "date_from": target,
                "date_to": target,
                "provider_id": data["provider"]["id"],
            },
            headers=HEADERS,
        )

        assert resp.status_code == 200
        for entry in resp.json()["schedule"]:
            assert entry["provider_id"] == data["provider"]["id"]

    async def test_filter_by_nonexistent_provider_returns_empty(self, client):
        """Filtering by a non-existent provider returns empty schedule."""
        await _seed_via_api(client)
        target = _next_weekday(0).isoformat()

        resp = await client.get(
            "/api/schedule",
            params={
                "date_from": target,
                "date_to": target,
                "provider_id": "00000000-0000-0000-0000-000000000099",
            },
            headers=HEADERS,
        )

        assert resp.status_code == 200
        assert resp.json()["schedule"] == []
