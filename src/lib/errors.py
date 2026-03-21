"""Structured error handling for the API layer.

Defines ``AppError`` (the application-wide exception) and
``register_error_handlers()`` which wires up FastAPI exception handlers
to produce the standard JSON error envelope:

    {"error": {"code": "...", "message": "...", "details": [...]}}
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Application-level error with a structured response body."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details: list = details or []
        super().__init__(message)


def _error_envelope(code: str, message: str, details: list | None = None) -> dict:
    """Build the canonical error JSON shape."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    """Attach exception handlers to *app*."""

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError,
    ) -> JSONResponse:
        details = [
            {"field": ".".join(str(loc) for loc in e["loc"]), "reason": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_envelope("VALIDATION_ERROR", "Request validation failed", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(
        request: Request, exc: StarletteHTTPException,
    ) -> JSONResponse:
        # If detail is already an error envelope dict, use it directly
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(
                f"HTTP_{exc.status_code}",
                str(exc.detail) if exc.detail else "HTTP error",
            ),
        )

    @app.exception_handler(Exception)
    async def _generic_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_envelope("INTERNAL_ERROR", "An unexpected error occurred"),
        )
