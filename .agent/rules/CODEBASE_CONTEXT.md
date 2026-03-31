# Healthcare Appointment Slot Optimizer — Codebase Context

> Last updated: 2026-03-31 (template sync)
> Template synced: 2026-03-31

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
│   ├── main.py                      # FastAPI app factory + lifespan
│   ├── config.py                    # Pydantic Settings
│   ├── optimizer/                   # (Phase 3 — not yet implemented)
│   ├── booking/                     # (Phase 4 — not yet implemented)
│   ├── api/
│   │   ├── config_routes.py         # Provider/room/type/availability/rules CRUD
│   │   ├── health.py                # GET /api/health (public)
│   │   ├── schemas/
│   │   │   └── config_schemas.py    # Pydantic models + RoomType enum
│   │   └── middleware/
│   │       ├── auth.py              # API key validation dependency
│   │       └── rate_limiter.py      # Sliding-window rate limiter
│   ├── db/
│   │   ├── session.py               # Async engine (lru_cache) + session factory
│   │   └── models.py                # SQLAlchemy models (6 tables)
│   └── lib/
│       ├── errors.py                # AppError + JSON error envelope
│       ├── time_utils.py            # Interval math for slot computation
│       ├── logger.py                # Structured logging (structlog)
│       └── scheduler.py             # APScheduler factory
├── alembic/
│   └── versions/                    # Initial migration (all 6 tables)
├── tests/
│   ├── conftest.py                  # Shared fixtures (async engine/session)
│   ├── unit/
│   │   ├── test_auth.py
│   │   ├── test_config.py
│   │   ├── test_errors.py
│   │   ├── test_health.py
│   │   ├── test_logger.py
│   │   ├── test_rate_limiter.py
│   │   ├── test_scheduler.py
│   │   └── test_time_utils.py
│   └── integration/
│       ├── test_smoke.py            # DB connectivity check
│       ├── test_models.py           # ORM model CRUD
│       ├── test_health.py           # Health endpoint integration
│       └── test_config_api.py       # Config API (23 tests)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── .env.example
└── docs/
    └── appointment-slot-optimizer_prd.md
```

## Key Modules

| Module | Purpose | Key Files |
|--------|---------|-----------|
| api | HTTP layer — config CRUD, health, auth middleware | `src/api/config_routes.py`, `src/api/health.py`, `src/api/middleware/` |
| api/schemas | Pydantic request/response models | `src/api/schemas/config_schemas.py` |
| db | Database models + async session factory | `src/db/models.py`, `src/db/session.py` |
| lib | Shared utilities — errors, logging, time, scheduler | `src/lib/errors.py`, `src/lib/logger.py`, `src/lib/time_utils.py`, `src/lib/scheduler.py` |
| optimizer | Slot computation (Phase 3 — not yet implemented) | `src/optimizer/` |
| booking | Booking service (Phase 4 — not yet implemented) | `src/booking/` |

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
| DATABASE_URL | PostgreSQL connection string (port 5434 on dev — see Gotchas) | `.env` |
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
| Docker up | `docker compose up -d` (Postgres binds to host port **5434**) |

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
| 2026-03-21 | Docker | Native PostgreSQL runs on port 5432; Docker Compose maps to **5434** to coexist. `DATABASE_URL` must use port 5434 for local dev. | Phase 0 setup |
| 2026-03-22 | Tests | `async_engine` fixture MUST be **function-scoped** (not session-scoped). Session-scoped causes asyncpg `InterfaceError: another operation is in progress` on 2nd+ test. | Phase 2 config API |
| 2026-03-22 | Tests | `get_engine` uses `@lru_cache`. The lifespan's `engine.dispose()` poisons it — `_clear_engine_cache` autouse fixture clears it between tests. | Phase 2 config API |

## Shared Foundation (MUST READ before any implementation)

> These files define the project's shared patterns, configuration, and utilities.
> The AI MUST read these **in full** before writing ANY new code. Never recreate what exists here.

| Category | File(s) | What it establishes |
|----------|---------|-------------------|
| Config | `src/config.py` | Pydantic Settings, all env vars, defaults |
| DB session | `src/db/session.py` | Async SQLAlchemy engine (lru_cache) + session factory |
| DB models | `src/db/models.py` | All SQLAlchemy models, base class, 6 tables |
| Error handling | `src/lib/errors.py` | AppError class + JSON error envelope handler |
| Auth middleware | `src/api/middleware/auth.py` | API key validation dependency |
| Schemas | `src/api/schemas/config_schemas.py` | Pydantic models for all config entities + RoomType enum |
| Logger | `src/lib/logger.py` | Structured logging with structlog |
| Time utils | `src/lib/time_utils.py` | Interval math for slot computation |
| Scheduler | `src/lib/scheduler.py` | APScheduler BackgroundScheduler factory |
| Pagination | `src/lib/pagination.py` | PaginationParams + get_pagination dependency (page/page_size/offset) |
| Seed data | `src/db/seed.py` | Idempotent dev seed: 5 providers, 8 rooms, 6 types, ~220 bookings |
| Test fixtures | `tests/conftest.py` | Async engine/session fixtures with rollback isolation |

## Deep References

> For detailed implementation patterns, read the source directly — don't embed here.

| Topic | Where to look |
|-------|--------------|
| Slot optimizer logic | `src/optimizer/` |
| Booking service | `src/booking/` |
| API routes & CRUD | `src/api/config_routes.py`, `src/api/health.py` |
| Pydantic schemas | `src/api/schemas/config_schemas.py` |
| Database models | `src/db/models.py` |
| Test patterns | `tests/` |
| Deployment config | `Dockerfile`, `docker-compose.yml` |
| Migrations | `alembic/versions/` |
