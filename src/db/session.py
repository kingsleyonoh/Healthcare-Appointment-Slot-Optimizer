"""Async database session factory.

Provides ``get_session()`` async generator for use as a FastAPI
dependency, and ``get_engine()`` for creating the engine singleton.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings


@lru_cache(maxsize=1)
def get_engine():
    """Create and cache the async SQLAlchemy engine."""
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=(settings.ENV == "development"),
        pool_size=5,
        max_overflow=10,
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to the cached engine."""
    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    The session commits on success; rolls back on exception.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
