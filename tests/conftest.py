"""Shared test fixtures for the Healthcare Appointment Slot Optimizer."""

import os
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


def _load_dotenv() -> None:
    """Load .env file from project root if python-dotenv is available."""
    try:
        from dotenv import load_dotenv

        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass  # python-dotenv not installed; rely on env vars


_load_dotenv()

_DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://postgres:devpass@localhost:5434/scheduler"
)


def get_test_database_url() -> str:
    """Get the database URL for testing.

    Uses TEST_DATABASE_URL if set, otherwise falls back to DATABASE_URL.
    """
    return os.getenv(
        "TEST_DATABASE_URL",
        os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL),
    )


@pytest.fixture(scope="session")
def database_url() -> str:
    """Provide the test database URL."""
    return get_test_database_url()


@pytest.fixture
async def async_engine(database_url: str):
    """Create a function-scoped async engine for full test isolation."""
    engine = create_async_engine(database_url, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine) -> AsyncSession:
    """Provide an async DB session with automatic rollback after each test.

    Opens a connection, starts a transaction, binds a session to it, and
    rolls the transaction back after the test finishes — leaving the DB
    unchanged.
    """
    async with async_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture(autouse=True)
def _clear_engine_cache():
    """Clear the lru_cache on get_engine between tests.

    Without this, the lifespan's ``engine.dispose()`` poisons the cache
    and subsequent tests get ``RuntimeError: Event loop is closed``.
    """
    from src.db.session import get_engine

    get_engine.cache_clear()
    yield
    get_engine.cache_clear()


@pytest.fixture(autouse=True)
async def _clean_db(database_url):
    """Truncate all application tables before each test.

    Prevents stale data from previous runs from polluting test isolation.
    Uses TRUNCATE ... CASCADE for foreign-key safety.
    """
    from sqlalchemy import text

    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE bookings, overbooking_rules, "
                "provider_availability, appointment_types, rooms, providers "
                "CASCADE"
            )
        )
    await engine.dispose()
