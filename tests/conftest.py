"""Shared test fixtures for the Healthcare Appointment Slot Optimizer."""

import os
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


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


@pytest.fixture(scope="session")
def async_engine(database_url: str):
    """Create an async SQLAlchemy engine for tests (session-scoped)."""
    engine = create_async_engine(database_url, echo=False)
    yield engine
    # Engine disposal is handled by the event loop cleanup


@pytest.fixture
async def async_session(async_engine) -> AsyncSession:
    """Provide an async DB session with automatic rollback after each test."""
    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()
