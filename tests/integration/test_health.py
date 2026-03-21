"""Integration tests for the health endpoint and FastAPI app bootstrap."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test GET /api/health endpoint."""

    def test_health_returns_200(self):
        """Health endpoint should return 200 with status and version."""
        from src.main import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "version" in body

    def test_health_no_auth_required(self):
        """Health endpoint should be accessible without API key."""
        from src.main import create_app

        app = create_app()
        client = TestClient(app)
        # No X-API-Key header
        resp = client.get("/api/health")
        assert resp.status_code == 200


class TestAppBootstrap:
    """Test that the FastAPI application bootstraps correctly."""

    def test_create_app_returns_fastapi_instance(self):
        """create_app() should return a FastAPI application."""
        from fastapi import FastAPI

        from src.main import create_app

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_has_title(self):
        """App should have a descriptive title."""
        from src.main import create_app

        app = create_app()
        assert app.title  # not empty
        assert "Appointment" in app.title or "Healthcare" in app.title
