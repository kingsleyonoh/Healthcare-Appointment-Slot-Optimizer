# Healthcare Appointment Slot Optimizer — Codebase Context

> Last updated: 2026-04-10
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
| HTTP Client | httpx (async, for Notification Hub) |
| Test Runner | pytest + httpx (async) |
| Background Jobs | APScheduler 3.x (in-process, hourly interval) |
| Containerization | Docker + Docker Compose |
| Hosting | Docker on Hetzner VPS behind Traefik |
| Logging | structlog (JSON to stdout) |

## Project Structure

```
appointment-slot-optimizer/
├── src/
│   ├── main.py                      # App factory + lifespan + job registration
│   ├── config.py                    # Pydantic Settings (all env vars)
│   ├── optimizer/
│   │   ├── engine.py                # Slot computation orchestrator
│   │   ├── constraints.py           # Availability windows, buffers, room filtering
│   │   └── scorer.py                # Quality scoring (preference/gap/room/overbook)
│   ├── booking/
│   │   ├── service.py               # create/get/list/cancel booking
│   │   └── backfill.py              # Backfill candidates (±7 days proximity)
│   ├── integrations/
│   │   └── notification_hub.py      # Fire-and-forget event emitter (HTTP)
│   ├── jobs/
│   │   ├── no_show_marker.py        # Mark overdue bookings as no_show (hourly)
│   │   └── stats_calculator.py      # Compute utilization stats (hourly)
│   ├── api/
│   │   ├── config_routes.py         # Provider/room/type/availability/rules CRUD
│   │   ├── booking_routes.py        # Booking CRUD + cancel + backfill
│   │   ├── slots.py                 # GET /api/slots (scored slot computation)
│   │   ├── schedule.py              # GET /api/schedule (daily breakdown)
│   │   ├── stats.py                 # GET /api/stats (utilization metrics)
│   │   ├── health.py                # GET /api/health (public)
│   │   ├── schemas/
│   │   │   ├── config_schemas.py    # Config entity models + RoomType enum
│   │   │   ├── booking_schemas.py   # Booking + cancel + backfill schemas
│   │   │   ├── slot_schemas.py      # SlotOut, SlotResponse
│   │   │   └── schedule_schemas.py  # Schedule view schemas
│   │   └── middleware/
│   │       ├── auth.py              # API key validation dependency
│   │       └── rate_limiter.py      # Sliding-window rate limiter
│   ├── db/
│   │   ├── session.py               # Async engine (lru_cache) + session factory
│   │   ├── models.py                # SQLAlchemy models (6 tables)
│   │   └── seed.py                  # Idempotent dev seed data
│   └── lib/
│       ├── errors.py                # AppError + JSON error envelope
│       ├── time_utils.py            # Interval math for slot computation
│       ├── logger.py                # Structured logging (structlog)
│       ├── cache.py                 # In-memory TTL cache (AvailabilityCache)
│       ├── pagination.py            # PaginationParams + get_pagination
│       └── scheduler.py             # APScheduler factory
├── alembic/versions/                # Initial migration (all 6 tables)
├── tests/
│   ├── conftest.py                  # Shared async engine/session fixtures
│   ├── unit/                        # 14 unit test files
│   └── integration/                 # 7 integration test files
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── .env.example
└── docs/
    └── appointment-slot-optimizer_prd.md
```

## Key Modules

| Module | Purpose | → Deep Reference |
|--------|---------|-----------------|
| optimizer | Constraint-based slot computation with quality scoring | `src/optimizer/` |
| booking | Booking CRUD, idempotency, cancellation, backfill candidates | `src/booking/` |
| integrations | Notification Hub fire-and-forget event emitter | `src/integrations/` |
| jobs | Background jobs: no-show marker, stats calculator (hourly) | `src/jobs/` |
| api | HTTP layer — config, bookings, slots, schedule, stats, health | `src/api/` |
| api/schemas | Pydantic request/response models for all endpoints | `src/api/schemas/` |
| db | Database models + async session factory | `src/db/` |
| lib | Shared utilities — errors, logging, time, cache, pagination, scheduler | `src/lib/` |

## Database Schema

6 tables — all UUID PKs, `created_at`/`updated_at` timestamps. → see `src/db/models.py`

| Table | Purpose |
|-------|---------|
| providers | Doctor records (name, specialty, max_daily, buffer_minutes, enabled) |
| rooms | Physical rooms (name, room_type, equipment[], enabled) |
| appointment_types | Duration + room requirements |
| provider_availability | Weekly windows (day_of_week, start/end_time, valid_from/until) |
| bookings | Appointments (request_id unique, patient_name/email, 3 FKs, date/times, status) |
| overbooking_rules | Per-provider/type overbook limits |

**Unique:** `uq_provider_slot`, `uq_room_slot` (prevent double-booking)

## External Integrations

| Service | Purpose | Auth Method |
|---------|---------|------------|
| Notification Hub | Fire-and-forget events (appointment.booked, .cancelled, .no_show) | API key in `X-API-Key` header |
| BetterStack | External health monitoring (polls GET /api/health) | Heartbeat URL |

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| HOST, PORT, ENV | Server bind, port, mode | 0.0.0.0, 8000, development |
| API_KEYS | Comma-separated valid API keys | (required) |
| DATABASE_URL | PostgreSQL connection (port **5434** on dev) | (required) |
| SLOT_INCREMENT_MINUTES | Slot generation interval | 15 |
| DEFAULT_BUFFER_MINUTES | Buffer between appointments | 10 |
| MAX_DAILY_APPOINTMENTS | Per-provider daily limit | 20 |
| OVERBOOK_DEFAULT | Default overbook limit | 0 |
| NOTIFICATION_HUB_URL/API_KEY/ENABLED | Hub base URL, key, toggle | "", "", false |
| BETTERSTACK_HEARTBEAT_URL | External health monitor | "" |
| LOG_LEVEL | Logging verbosity | info |

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

- Error format: `{ "error": { "code", "message", "details" } }` via AppError
- Auth: `X-API-Key` header, middleware dependency
- Pagination: Offset-based, `page` + `page_size` (default 25, max 100)
- IDs: UUID via `gen_random_uuid()` | Timestamps: `created_at`/`updated_at`
- Slots: Real-time computation, never stored | Double-booking: DB UNIQUE constraints
- Idempotency: `request_id` on bookings | Backfill: +/-7 days proximity on cancel
- Cache: In-memory TTL 60s for availability | Jobs: APScheduler hourly, `asyncio.run()`
- Events: Fire-and-forget via NotificationHubClient (never blocks booking)
- Scoring: 0.0-1.0 weighted: preference 40%, gap 35%, room 15%, overbook 10%

## Gotchas & Lessons Learned

| Area | Gotcha |
|------|--------|
| Docker | Postgres maps to port **5434** (not 5432) to coexist with native install |
| Tests | `async_engine` fixture MUST be **function-scoped** — session-scoped causes asyncpg `InterfaceError` |
| Tests | `get_engine` uses `@lru_cache` — `_clear_engine_cache` autouse fixture clears it between tests |

## Shared Foundation (MUST READ before any implementation)

> These files define the project's shared patterns. Read **in full** before writing new code.

| Category | File(s) | What it establishes |
|----------|---------|-------------------|
| Config + DB | `src/config.py`, `src/db/session.py`, `src/db/models.py` | Settings, async engine, 6-table schema |
| Error + Auth | `src/lib/errors.py`, `src/api/middleware/auth.py` | AppError envelope + API key dependency |
| Schemas | `src/api/schemas/*.py` | Pydantic models for config, booking, slot, schedule |
| Lib utilities | `src/lib/` (all files) | Logger, time math, TTL cache, pagination, scheduler |
| Optimizer | `src/optimizer/constraints.py`, `src/optimizer/scorer.py` | Availability windows, buffers, room filtering, scoring |
| Booking | `src/booking/service.py`, `src/booking/backfill.py` | CRUD + validation, backfill candidates |
| Integrations | `src/integrations/notification_hub.py` | Fire-and-forget event emitter |
| Seed + Tests | `src/db/seed.py`, `tests/conftest.py` | Dev seed data, async test fixtures |

## Deep References

> For detailed implementation, read the source directly.

| Topic | Where to look |
|-------|--------------|
| Slot optimizer logic | `src/optimizer/` |
| Booking service | `src/booking/` |
| Notification Hub integration | `src/integrations/notification_hub.py` |
| Background jobs | `src/jobs/` |
| Config CRUD routes | `src/api/config_routes.py` |
| Booking routes | `src/api/booking_routes.py` |
| Slots API | `src/api/slots.py` |
| Schedule API | `src/api/schedule.py` |
| Stats API | `src/api/stats.py` |
| Pydantic schemas | `src/api/schemas/` |
| Database models | `src/db/models.py` |
| Test patterns | `tests/` |
| Deployment config | `Dockerfile`, `docker-compose.yml` |
| Migrations | `alembic/versions/` |
