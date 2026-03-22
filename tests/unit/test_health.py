"""Tests for health endpoint — src/api/health.py."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app


@pytest.fixture
def app():
    """Create a fresh app instance for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Synchronous test client (unused — kept for parity)."""
    from starlette.testclient import TestClient

    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    """Verify GET /api/health behaviour."""

    def test_health_returns_200(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_includes_version(self, client):
        response = client.get("/api/health")
        body = response.json()
        assert "version" in body
        assert body["version"] == "0.1.0"

    def test_health_no_auth_required(self, client):
        """Health endpoint must be accessible without X-API-Key."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_includes_status_field(self, client):
        response = client.get("/api/health")
        body = response.json()
        assert "status" in body
        assert body["status"] in ("healthy", "degraded")

    def test_health_includes_database_field(self, client):
        """Health response must include a database connectivity indicator."""
        response = client.get("/api/health")
        body = response.json()
        assert "database" in body
        assert body["database"] in ("connected", "disconnected")
