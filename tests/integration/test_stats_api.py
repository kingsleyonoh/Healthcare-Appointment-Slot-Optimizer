"""Integration tests for GET /api/stats endpoint."""

from __future__ import annotations

import uuid
from datetime import date, time, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app

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
    """Create prerequisite data via API endpoints."""
    resp = await client.post(
        "/api/providers",
        json={"name": f"Dr. Stats-{uuid.uuid4().hex[:6]}", "specialty": "General"},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    provider = resp.json()

    resp = await client.post(
        "/api/rooms",
        json={"name": f"StatsRoom-{uuid.uuid4().hex[:6]}", "room_type": "consultation"},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    room = resp.json()

    resp = await client.post(
        "/api/appointment-types",
        json={
            "name": f"StatsCheck-{uuid.uuid4().hex[:6]}",
            "duration_minutes": 30,
            "required_room_type": "consultation",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    appt_type = resp.json()

    today = date.today()
    dow = today.weekday()
    resp = await client.post(
        "/api/availability",
        json={
            "provider_id": provider["id"],
            "day_of_week": dow,
            "start_time": "08:00",
            "end_time": "17:00",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201

    return {"provider": provider, "room": room, "appt_type": appt_type}


class TestStatsEndpoint:
    """GET /api/stats integration tests."""

    async def test_stats_returns_200_with_correct_shape(self, client):
        """Stats endpoint returns all required fields."""
        resp = await client.get("/api/stats", headers=HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert "utilization_today" in body
        assert "bookings_today" in body
        assert "no_shows" in body

    async def test_stats_reflects_bookings_today(self, client):
        """After creating a booking, bookings_today increments."""
        data = await _seed_via_api(client)
        today = date.today().isoformat()

        await client.post(
            "/api/bookings",
            json={
                "request_id": f"stats-bk-{uuid.uuid4().hex[:8]}",
                "patient_name": "StatsPatient",
                "provider_id": data["provider"]["id"],
                "room_id": data["room"]["id"],
                "appointment_type_id": data["appt_type"]["id"],
                "date": today,
                "start_time": "09:00",
            },
            headers=HEADERS,
        )

        resp = await client.get("/api/stats", headers=HEADERS)

        assert resp.status_code == 200
        assert resp.json()["bookings_today"] >= 1

    async def test_stats_no_auth_returns_401(self, client):
        """Stats endpoint requires API key."""
        resp = await client.get("/api/stats")
        assert resp.status_code == 401

    async def test_stats_empty_database_returns_zeros(self, client):
        """Empty database returns all zeros."""
        resp = await client.get("/api/stats", headers=HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["bookings_today"] == 0
        assert body["no_shows"] == 0
        assert body["utilization_today"] == 0.0

    async def test_stats_utilization_is_numeric(self, client):
        """utilization_today is a float between 0 and 1."""
        resp = await client.get("/api/stats", headers=HEADERS)

        assert resp.status_code == 200
        util = resp.json()["utilization_today"]
        assert isinstance(util, (int, float))
        assert 0.0 <= util <= 1.0
