"""In-memory sliding-window rate limiter middleware.

Tracks request counts per client IP within a rolling window.
Suitable for single-process deployments; replace with Redis-backed
implementation for multi-process / production.
"""

from __future__ import annotations

import time as _time
from collections import defaultdict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter."""

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = 200,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        """Extract the client IP from the request."""
        if request.client:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check rate limit before forwarding the request."""
        client = self._client_ip(request)
        now = _time.monotonic()
        cutoff = now - self.window_seconds

        # Prune old entries
        self._requests[client] = [
            ts for ts in self._requests[client] if ts > cutoff
        ]

        if len(self._requests[client]) >= self.max_requests:
            retry_after = int(
                self.window_seconds
                - (now - self._requests[client][0])
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests",
                        "details": [],
                    }
                },
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self._requests[client].append(now)
        return await call_next(request)
