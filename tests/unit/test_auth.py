"""Unit tests for src.api.middleware.auth — API key authentication."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestApiKeyAuth:
    """Test the API key authentication dependency."""

    def _build_app(self, api_keys: list[str]):
        """Helper: create a minimal FastAPI app with the auth dependency."""
        from src.api.middleware.auth import create_api_key_dependency
        from src.lib.errors import register_error_handlers

        app = FastAPI()
        register_error_handlers(app)
        verify = create_api_key_dependency(api_keys)

        @app.get("/protected")
        async def protected(key=verify):
            return {"status": "ok"}

        return app

    def test_valid_key_passes(self):
        """Request with a valid X-API-Key header should succeed."""
        app = self._build_app(["test-key-1", "test-key-2"])
        client = TestClient(app)
        resp = client.get("/protected", headers={"X-API-Key": "test-key-1"})
        assert resp.status_code == 200

    def test_invalid_key_returns_401(self):
        """Request with an invalid API key should return 401."""
        app = self._build_app(["valid-key"])
        client = TestClient(app)
        resp = client.get("/protected", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_missing_key_returns_401(self):
        """Request without X-API-Key header should return 401."""
        app = self._build_app(["valid-key"])
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 401

    def test_error_uses_json_envelope(self):
        """Auth failures should use the standard error JSON envelope."""
        app = self._build_app(["valid-key"])
        client = TestClient(app)
        resp = client.get("/protected", headers={"X-API-Key": "bad"})
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "UNAUTHORIZED"
