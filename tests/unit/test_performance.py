"""Performance tests — slot computation and concurrent booking safety.

Performance benchmark: slot computation for all providers in a single
day completes under 500ms (PRD Section 10b, 15).

Concurrent booking stress test: verify no double-bookings under parallel
requests (PRD Section 15).
"""

from __future__ import annotations

import asyncio
import time as _time
import uuid
from datetime import date, time, timedelta

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


async def _seed_performance_data(client) -> dict:
    """Seed 5 providers, 8 rooms, 3 appointment types for perf test."""
    providers = []
    for i in range(5):
        resp = await client.post(
            "/api/providers",
            json={
                "name": f"Dr. Perf-{i}",
                "specialty": "General",
                "max_daily_appointments": 20,
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201
        providers.append(resp.json())

    rooms = []
    for i in range(8):
        resp = await client.post(
            "/api/rooms",
            json={
                "name": f"PerfRoom-{i}",
                "room_type": "consultation",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201
        rooms.append(resp.json())

    appt_types = []
    for i, dur in enumerate([15, 30, 60]):
        resp = await client.post(
            "/api/appointment-types",
            json={
                "name": f"PerfType-{i}",
                "duration_minutes": dur,
                "required_room_type": "consultation",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201
        appt_types.append(resp.json())

    # Availability for all providers on Monday 08:00-17:00
    for prov in providers:
        resp = await client.post(
            "/api/availability",
            json={
                "provider_id": prov["id"],
                "day_of_week": 0,
                "start_time": "08:00",
                "end_time": "17:00",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201

    # Seed some existing bookings for realism
    target = _next_weekday(0).isoformat()
    for i, prov in enumerate(providers[:3]):
        for j, hour in enumerate([9, 10, 11]):
            room_idx = i * 3 + j
            if room_idx < len(rooms):
                await client.post(
                    "/api/bookings",
                    json={
                        "request_id": f"perf-bk-{i}-{j}",
                        "patient_name": f"PerfPatient-{i}-{j}",
                        "provider_id": prov["id"],
                        "room_id": rooms[room_idx]["id"],
                        "appointment_type_id": appt_types[1]["id"],
                        "date": target,
                        "start_time": f"{hour:02d}:00",
                    },
                    headers=HEADERS,
                )

    return {
        "providers": providers,
        "rooms": rooms,
        "appt_types": appt_types,
    }


class TestPerformanceBenchmark:
    """Slot computation for all providers in a single day < 500ms."""

    async def test_slot_computation_under_500ms(self, client):
        """GET /api/slots with realistic data completes under 500ms."""
        data = await _seed_performance_data(client)
        target = _next_weekday(0).isoformat()

        start = _time.perf_counter()
        resp = await client.get(
            "/api/slots",
            params={
                "target_date": target,
                "appointment_type_id": data["appt_types"][1]["id"],
            },
            headers=HEADERS,
        )
        elapsed_ms = (_time.perf_counter() - start) * 1000

        assert resp.status_code == 200
        assert elapsed_ms < 500, f"Slot computation took {elapsed_ms:.0f}ms (limit: 500ms)"

    async def test_slots_return_results_for_multiple_providers(self, client):
        """Realistic slot query returns slots from multiple providers."""
        data = await _seed_performance_data(client)
        target = _next_weekday(0).isoformat()

        resp = await client.get(
            "/api/slots",
            params={
                "target_date": target,
                "appointment_type_id": data["appt_types"][0]["id"],  # 15-min type
            },
            headers=HEADERS,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["slots"]) > 0


class TestConcurrentBookingStress:
    """Verify no double-bookings under parallel requests."""

    async def test_10_concurrent_bookings_same_slot_only_one_wins(self, client):
        """10 parallel requests for the same slot — exactly 1 succeeds."""
        data = await _seed_performance_data(client)
        target = _next_weekday(0).isoformat()

        # All target the same provider + room + time
        payloads = [
            {
                "request_id": f"stress-{i}-{uuid.uuid4().hex[:8]}",
                "patient_name": f"StressPatient-{i}",
                "provider_id": data["providers"][4]["id"],  # Last provider (no bookings)
                "room_id": data["rooms"][7]["id"],  # Last room
                "appointment_type_id": data["appt_types"][0]["id"],
                "date": target,
                "start_time": "15:00",
            }
            for i in range(10)
        ]

        responses = await asyncio.gather(
            *(
                client.post("/api/bookings", json=p, headers=HEADERS)
                for p in payloads
            )
        )

        statuses = [r.status_code for r in responses]
        success_count = statuses.count(201)
        conflict_count = statuses.count(409)

        assert success_count == 1, f"Expected 1 success, got {success_count}: {statuses}"
        assert conflict_count == 9, f"Expected 9 conflicts, got {conflict_count}: {statuses}"
