"""Smoke test: verify PostgreSQL connectivity."""

from sqlalchemy import text


async def test_database_connectivity(async_session):
    """Verify that the test database accepts connections and executes queries."""
    result = await async_session.execute(text("SELECT 1 AS ping"))
    row = result.scalar_one()
    assert row == 1
