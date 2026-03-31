"""Seed the database with sample data for development.

Creates 5 providers, 8 rooms, 6 appointment types, availability windows,
and 2 weeks of sample bookings. Idempotent: skips if providers already exist.

Usage:
    python -m src.db.seed
"""

from __future__ import annotations

import asyncio
import random
from datetime import date, time, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.config import get_settings
from src.db.models import (
    AppointmentType,
    Booking,
    OverbookingRule,
    Provider,
    ProviderAvailability,
    Room,
)

# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

PROVIDERS = [
    {"name": "Dr. Sarah Chen", "specialty": "General Practice", "max_daily_appointments": 20, "buffer_minutes": 10},
    {"name": "Dr. James Wilson", "specialty": "Cardiology", "max_daily_appointments": 12, "buffer_minutes": 15},
    {"name": "Dr. Maria Garcia", "specialty": "Dermatology", "max_daily_appointments": 18, "buffer_minutes": 5},
    {"name": "Dr. David Kim", "specialty": "Orthopedics", "max_daily_appointments": 10, "buffer_minutes": 20},
    {"name": "Dr. Emily Taylor", "specialty": "Pediatrics", "max_daily_appointments": 22, "buffer_minutes": 10},
]

ROOMS = [
    {"name": "Consultation A", "room_type": "consultation", "equipment": []},
    {"name": "Consultation B", "room_type": "consultation", "equipment": []},
    {"name": "Exam Room 1", "room_type": "examination", "equipment": ["blood_pressure", "otoscope"]},
    {"name": "Exam Room 2", "room_type": "examination", "equipment": ["blood_pressure", "otoscope"]},
    {"name": "Procedure Room 1", "room_type": "procedure", "equipment": ["ecg", "ultrasound"]},
    {"name": "Procedure Room 2", "room_type": "procedure", "equipment": ["ecg"]},
    {"name": "Lab Room", "room_type": "general", "equipment": ["centrifuge", "microscope"]},
    {"name": "General Room", "room_type": "general", "equipment": []},
]

APPOINTMENT_TYPES = [
    {"name": "General Checkup", "duration_minutes": 30, "required_room_type": "consultation", "required_equipment": []},
    {"name": "Follow-Up Visit", "duration_minutes": 15, "required_room_type": "consultation", "required_equipment": []},
    {"name": "Physical Exam", "duration_minutes": 45, "required_room_type": "examination", "required_equipment": ["blood_pressure"]},
    {"name": "ECG Test", "duration_minutes": 30, "required_room_type": "procedure", "required_equipment": ["ecg"]},
    {"name": "Ultrasound", "duration_minutes": 45, "required_room_type": "procedure", "required_equipment": ["ultrasound"]},
    {"name": "Lab Work", "duration_minutes": 20, "required_room_type": "general", "required_equipment": []},
]

PATIENT_NAMES = [
    "Alice Johnson", "Bob Martinez", "Carol White", "Dan Brown",
    "Eve Davis", "Frank Miller", "Grace Lee", "Henry Wang",
    "Iris Patel", "Jack Thompson",
]


async def seed(database_url: str | None = None) -> None:
    """Insert seed data. Skips if providers table is not empty."""
    url = database_url or get_settings().DATABASE_URL
    engine = create_async_engine(url, echo=False)

    async with engine.begin() as conn:
        # Use raw connection for the count check
        result = await conn.execute(
            text("SELECT count(*) FROM providers")
        )
        count = result.scalar_one()
        if count > 0:
            print(f"Database already has {count} providers — skipping seed.")
            await engine.dispose()
            return

    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            # --- Providers ---
            providers = [Provider(**p) for p in PROVIDERS]
            session.add_all(providers)
            await session.flush()

            # --- Rooms ---
            rooms = [Room(**r) for r in ROOMS]
            session.add_all(rooms)
            await session.flush()

            # --- Appointment Types ---
            appt_types = [AppointmentType(**a) for a in APPOINTMENT_TYPES]
            session.add_all(appt_types)
            await session.flush()

            # --- Provider Availability (Mon-Fri, 08:00-17:00 for all) ---
            for provider in providers:
                for dow in range(5):  # Monday=0 to Friday=4
                    session.add(ProviderAvailability(
                        provider_id=provider.id,
                        day_of_week=dow,
                        start_time=time(8, 0),
                        end_time=time(17, 0),
                    ))
            await session.flush()

            # --- Overbooking rules ---
            # Global: allow 1 overbook, plus provider-specific for Dr. Chen
            session.add(OverbookingRule(max_overbook=1, enabled=True))
            session.add(OverbookingRule(
                provider_id=providers[0].id,
                max_overbook=2,
                enabled=True,
            ))
            await session.flush()

            # --- Bookings (2 weeks from today) ---
            today = date.today()
            start_date = today
            end_date = today + timedelta(days=14)

            # Build lookup for rooms by type
            rooms_by_type: dict[str, list[Room]] = {}
            for room in rooms:
                rooms_by_type.setdefault(room.room_type, []).append(room)

            random.seed(42)  # Reproducible seed data
            booking_count = 0
            current = start_date
            while current <= end_date:
                dow = current.weekday()
                if dow >= 5:  # Skip weekends
                    current += timedelta(days=1)
                    continue

                # Track used slots per day across ALL providers
                used_provider_slots: set[tuple] = set()  # (provider_id, hour, minute)
                used_room_slots: set[tuple] = set()      # (room_id, hour, minute)

                for provider in providers:
                    # 3-5 bookings per provider per day
                    num_bookings = random.randint(3, 5)

                    for _ in range(num_bookings):
                        appt = random.choice(appt_types)
                        compatible = rooms_by_type.get(appt.required_room_type, [])
                        if not compatible:
                            continue

                        # Random start between 08:00 and 15:00 on 15-min increments
                        hour = random.randint(8, 15)
                        minute = random.choice([0, 15, 30, 45])

                        provider_key = (provider.id, hour, minute)
                        if provider_key in used_provider_slots:
                            continue

                        # Find a room not already booked at this time
                        random.shuffle(compatible)
                        room = None
                        for candidate in compatible:
                            room_key = (candidate.id, hour, minute)
                            if room_key not in used_room_slots:
                                room = candidate
                                break
                        if room is None:
                            continue

                        start_t = time(hour, minute)
                        end_minutes = hour * 60 + minute + appt.duration_minutes
                        end_h, end_m = divmod(end_minutes, 60)
                        if end_h >= 18:
                            continue
                        end_t = time(end_h, end_m)

                        used_provider_slots.add(provider_key)
                        used_room_slots.add((room.id, hour, minute))

                        status = random.choices(
                            ["confirmed", "completed", "cancelled", "no_show"],
                            weights=[50, 30, 15, 5],
                        )[0]

                        session.add(Booking(
                            request_id=f"seed-{current}-{provider.id}-{hour:02d}{minute:02d}",
                            patient_name=random.choice(PATIENT_NAMES),
                            patient_email=None,
                            provider_id=provider.id,
                            room_id=room.id,
                            appointment_type_id=appt.id,
                            date=current,
                            start_time=start_t,
                            end_time=end_t,
                            status=status,
                            cancellation_reason="Patient request" if status == "cancelled" else None,
                        ))
                        booking_count += 1

                current += timedelta(days=1)

            await session.flush()

    await engine.dispose()
    print(
        f"Seed complete: {len(PROVIDERS)} providers, {len(ROOMS)} rooms, "
        f"{len(APPOINTMENT_TYPES)} appointment types, {booking_count} bookings"
    )


if __name__ == "__main__":
    asyncio.run(seed())
