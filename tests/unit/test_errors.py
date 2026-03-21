"""Unit tests for src.lib.errors — structured error handling."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestAppError:
    """Test the AppError exception class."""

    def test_app_error_attributes(self):
        """AppError should store code, message, status_code, and details."""
        from src.lib.errors import AppError

        err = AppError(
            code="SLOT_UNAVAILABLE",
            message="No slots left",
            status_code=409,
            details=[{"field": "start_time", "reason": "Already booked"}],
        )
        assert err.code == "SLOT_UNAVAILABLE"
        assert err.message == "No slots left"
        assert err.status_code == 409
        assert len(err.details) == 1

    def test_app_error_default_status(self):
        """AppError should default to 400 status code."""
        from src.lib.errors import AppError

        err = AppError(code="BAD_INPUT", message="Invalid data")
        assert err.status_code == 400

    def test_app_error_default_details_empty(self):
        """AppError.details should default to an empty list."""
        from src.lib.errors import AppError

        err = AppError(code="TEST", message="test")
        assert err.details == []


class TestErrorHandler:
    """Test the error handler middleware integration."""

    def test_app_error_returns_json_envelope(self):
        """AppError should produce the standard error JSON envelope."""
        from src.lib.errors import AppError, register_error_handlers

        app = FastAPI()
        register_error_handlers(app)

        @app.get("/fail")
        async def fail():
            raise AppError(
                code="TEST_ERROR",
                message="Something broke",
                status_code=422,
            )

        client = TestClient(app)
        resp = client.get("/fail")
        assert resp.status_code == 422
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "TEST_ERROR"
        assert body["error"]["message"] == "Something broke"

    def test_unhandled_exception_returns_500(self):
        """Uncaught exceptions should return a generic 500 envelope."""
        from src.lib.errors import register_error_handlers

        app = FastAPI()
        register_error_handlers(app)

        @app.get("/crash")
        async def crash():
            raise RuntimeError("unexpected")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/crash")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"

    def test_validation_error_returns_422(self):
        """FastAPI validation errors should map to the error envelope."""
        from pydantic import BaseModel

        from src.lib.errors import register_error_handlers

        app = FastAPI()
        register_error_handlers(app)

        class Payload(BaseModel):
            count: int

        @app.post("/validate")
        async def validate(payload: Payload):
            return {"ok": True}

        client = TestClient(app)
        resp = client.post("/validate", json={"count": "not-a-number"})
        assert resp.status_code == 422
        body = resp.json()
        assert "error" in body
