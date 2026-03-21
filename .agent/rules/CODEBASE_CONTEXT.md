# Healthcare Appointment Slot Optimizer — Codebase Context

> Last updated: 2026-03-21
> Template synced: 2026-03-21

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Framework | FastAPI 0.115+ |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Test Runner | pytest + httpx (async) |
| Containerization | Docker + Docker Compose |
| Hosting | Docker on Hetzner VPS behind Traefik |
| Logging | structlog (JSON to stdout) |

## Project Structure

```
appointment-slot-optimizer/
├── src/
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # Pydantic Settings
│   ├── optimizer/
│   │   ├── engine.py                # Slot computation logic
│   │   ├── scorer.py                # Slot quality scoring
│   │   └── constraints.py           # Constraint evaluation
│   ├── booking/
│   │   ├── service.py               # Booking + cancellation logic
│   │   └── backfill.py              # Cancellation backfill
│   ├── api/
│   │   ├── slots.py                 # GET /api/slots
│   │   ├── bookings.py              # Booking CRUD
│   │   ├── schedule.py              # Schedule view
│   │   ├── config_routes.py         # Provider/room/type management
│   │   ├── health.py                # Health + stats
│   │   └── middleware/
│   │       ├── auth.py              # API key validation
│   │       └── errors.py            # Error handler
│   ├── db/
│   │   ├── session.py               # Async SQLAlchemy session
│   │   ├── models.py                # SQLAlchemy models
│   │   └── seed.py                  # Development seed data
│   └── lib/
│       ├── time_utils.py            # Time interval math
│       └── logger.py                # Structured logging
├── alembic/
│   └── versions/
├── tests/
│   ├── unit/
│   │   ├── test_optimizer.py
│   │   ├── test_scorer.py
│   │   └── test_booking.py
│   ├── integration/
│   │   ├── test_slots_api.py
│   │   └── test_bookings_api.py
│   └── conftest.py
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── .env.example
└── docs/
    └── prd.md
```

## Key Modules

| Module | Purpose | Key Files |
|--------|---------|-----------|
| optimizer | Computes available slots from constraints | `src/optimizer/engine.py`, `src/optimizer/scorer.py`, `src/optimizer/constraints.py` |
| booking | Creates/cancels bookings with conflict prevention | `src/booking/service.py`, `src/booking/backfill.py` |
| api | HTTP layer — routes, middleware, auth | `src/api/slots.py`, `src/api/bookings.py`, `src/api/middleware/` |
| db | Database models, session, seeds | `src/db/models.py`, `src/db/session.py`, `src/db/seed.py` |
| lib | Shared utilities | `src/lib/time_utils.py`, `src/lib/logger.py` |

## Database Schema

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| providers | Doctor/specialist records | id (UUID), name, specialty, max_daily_appointments, buffer_minutes, enabled |
| rooms | Physical rooms with types | id (UUID), name, room_type (enum), equipment (array), enabled |
| appointment_types | Defines duration and requirements | id (UUID), name, duration_minutes, required_room_type, required_equipment |
| provider_availability | Weekly schedule windows | provider_id (FK), day_of_week, start_time, end_time, valid_from, valid_until |
| bookings | Confirmed/cancelled appointments | request_id (unique), provider_id (FK), room_id (FK), date, start_time, end_time, status (enum) |
| overbooking_rules | Per-provider/type overbook limits | provider_id (FK nullable), appointment_type_id (FK nullable), max_overbook |

## External Integrations

| Service | Purpose | Auth Method |
|---------|---------|------------|
| None in v1 | Self-contained scheduling engine | N/A |

## Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| HOST | Server bind address | `.env` (default: 0.0.0.0) |
| PORT | Server port | `.env` (default: 8000) |
| ENV | Environment mode | `.env` (development/production) |
| API_KEYS | Comma-separated valid API keys | `.env` |
| DATABASE_URL | PostgreSQL connection string | `.env` |
| SLOT_INCREMENT_MINUTES | Slot generation interval | `.env` (default: 15) |
| DEFAULT_BUFFER_MINUTES | Buffer between appointments | `.env` (default: 10) |
| MAX_DAILY_APPOINTMENTS | Per-provider daily limit | `.env` (default: 20) |
| OVERBOOK_DEFAULT | Default overbook limit | `.env` (default: 0) |
| LOG_LEVEL | Logging verbosity | `.env` (default: info) |

## Commands

| Action | Command |
|--------|---------|
| Dev server | `uvicorn src.main:app --reload` |
| Run tests | `python -m pytest` |
| Run tests (coverage) | `python -m pytest --cov=src --cov-report=term-missing` |
| Lint/check | `ruff check .` |
| Format | `ruff format .` |
| Migrate DB | `alembic upgrade head` |
| New migration | `alembic revision --autogenerate -m "description"` |
| Seed data | `python -m src.db.seed` |
| Docker up | `docker compose up -d` |

## Key Patterns & Conventions

- File naming: `snake_case.py`
- Import order: stdlib → third-party → local (blank line between groups)
- Error handling: Consistent JSON error format `{ "error": { "code", "message", "details" } }`
- Auth: API key in `X-API-Key` header, validated by middleware
- Pagination: Offset-based with `page` + `page_size` query params (default 25, max 100)
- IDs: UUID (generated by database)
- Timestamps: `created_at` / `updated_at` on all resource tables
- Slots: Computed in real-time, never stored
- Booking safety: DB UNIQUE constraints prevent double-booking at data layer
- Idempotency: `request_id` on bookings prevents duplicate operations

## Gotchas & Lessons Learned

> Discovered during implementation. Added automatically by `/implement-next` Step 9.3.

| Date | Area | Gotcha | Discovered In |
|------|------|--------|---------------|
| | | | |

## Shared Foundation (MUST READ before any implementation)

> These files define the project's shared patterns, configuration, and utilities.
> The AI MUST read these **in full** before writing ANY new code. Never recreate what exists here.

| Category | File(s) | What it establishes |
|----------|---------|-------------------|
| Config | `src/config.py` | Pydantic Settings, all env vars, defaults |
| DB session | `src/db/session.py` | Async SQLAlchemy engine + session factory |
| DB models | `src/db/models.py` | All SQLAlchemy models, base class, enums |
| Error handling | `src/api/middleware/errors.py` | Centralized error types + HTTP error format |
| Auth middleware | `src/api/middleware/auth.py` | API key validation dependency |
| Logger | `src/lib/logger.py` | Structured logging with structlog |
| Time utils | `src/lib/time_utils.py` | Interval math for slot computation |
| Test fixtures | `tests/conftest.py` | Shared pytest fixtures, test DB setup |

## Deep References

> For detailed implementation patterns, read the source directly — don't embed here.

| Topic | Where to look |
|-------|--------------|
| Slot optimizer logic | `src/optimizer/` |
| Booking service | `src/booking/` |
| API routes | `src/api/` |
| Database models | `src/db/models.py` |
| Test patterns | `tests/` |
| Deployment config | `Dockerfile`, `docker-compose.prod.yml` |
| Migrations | `alembic/versions/` |
