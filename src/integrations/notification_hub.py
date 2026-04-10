"""Notification Hub client — fire-and-forget event emitter.

Sends events to the Event-Driven Notification Hub over HTTP.
All errors are swallowed so booking operations are never blocked.

Hub expects: ``{"event_type": "...", "event_id": "...", "payload": {...}}``
"""

from __future__ import annotations

import logging
import uuid

import httpx

logger = logging.getLogger(__name__)


class NotificationHubClient:
    """Async HTTP client for the Notification Hub."""

    def __init__(self, *, url: str, api_key: str, enabled: bool) -> None:
        self._url = url.rstrip("/") if url else ""
        self._api_key = api_key
        self._enabled = enabled

    async def emit(self, event_type: str, data: dict) -> None:
        """Fire-and-forget: POST an event to the hub. Never raises."""
        if not self._enabled or not self._url:
            return

        body = {
            "event_type": event_type,
            "event_id": f"{event_type}-{uuid.uuid4()}",
            "payload": data,
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self._url}/api/events",
                    json=body,
                    headers={"X-API-Key": self._api_key},
                    timeout=5.0,
                )
        except Exception:
            logger.warning(
                "Notification Hub emit failed for %s", event_type, exc_info=True,
            )
