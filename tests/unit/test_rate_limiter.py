"""Unit tests for src.api.middleware.rate_limiter — in-memory rate limiting."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestRateLimiter:
    """Test the sliding-window rate limiter middleware."""

    def _build_app(self, max_requests: int = 5, window_seconds: int = 60):
        """Helper: create a FastAPI app with the rate limiter applied."""
        from src.api.middleware.rate_limiter import RateLimiterMiddleware

        app = FastAPI()
        app.add_middleware(
            RateLimiterMiddleware,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        return app

    def test_requests_within_limit_succeed(self):
        """Requests under the limit should all return 200."""
        app = self._build_app(max_requests=3)
        client = TestClient(app)
        for _ in range(3):
            resp = client.get("/ping")
            assert resp.status_code == 200

    def test_exceeding_limit_returns_429(self):
        """Requests over the limit should return 429 Too Many Requests."""
        app = self._build_app(max_requests=2)
        client = TestClient(app)
        client.get("/ping")
        client.get("/ping")
        resp = client.get("/ping")
        assert resp.status_code == 429

    def test_429_uses_json_envelope(self):
        """Rate limit errors should use the standard error JSON envelope."""
        app = self._build_app(max_requests=1)
        client = TestClient(app)
        client.get("/ping")
        resp = client.get("/ping")
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "RATE_LIMITED"

    def test_retry_after_header_present(self):
        """429 responses should include a Retry-After header."""
        app = self._build_app(max_requests=1)
        client = TestClient(app)
        client.get("/ping")
        resp = client.get("/ping")
        assert "Retry-After" in resp.headers
