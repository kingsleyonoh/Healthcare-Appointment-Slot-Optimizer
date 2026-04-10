"""Unit tests for NotificationHubClient.

The Notification Hub is an EXTERNAL service — mocking httpx is correct here.
See CODING_STANDARDS_TESTING.md Mock Policy: "Mock ONLY third-party APIs."
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.integrations.notification_hub import NotificationHubClient


class TestNotificationHubEnabled:
    """Tests when the hub is enabled."""

    async def test_emit_sends_post_when_enabled(self):
        """Enabled client sends POST to the hub endpoint."""
        client = NotificationHubClient(
            url="http://hub.test", api_key="test-key", enabled=True,
        )

        with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock()

            await client.emit("appointment.booked", {"booking_id": "123"})

            mock_http.post.assert_called_once()
            call_args = mock_http.post.call_args
            assert call_args[0][0] == "http://hub.test/api/events"
            assert call_args[1]["headers"]["X-API-Key"] == "test-key"

    async def test_event_payload_structure(self):
        """Emitted payload includes event_type, event_id, and payload fields."""
        client = NotificationHubClient(
            url="http://hub.test", api_key="test-key", enabled=True,
        )

        with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock()

            await client.emit("appointment.cancelled", {"booking_id": "456", "reason": "patient request"})

            call_args = mock_http.post.call_args
            json_body = call_args[1]["json"]
            assert json_body["event_type"] == "appointment.cancelled"
            assert "event_id" in json_body
            assert json_body["event_id"].startswith("appointment.cancelled-")
            assert json_body["payload"]["booking_id"] == "456"
            assert json_body["payload"]["reason"] == "patient request"


class TestNotificationHubDisabled:
    """Tests when the hub is disabled."""

    async def test_emit_skips_when_disabled(self):
        """Disabled client makes no HTTP calls."""
        client = NotificationHubClient(
            url="http://hub.test", api_key="test-key", enabled=False,
        )

        with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
            await client.emit("appointment.booked", {"booking_id": "789"})

            mock_cls.assert_not_called()

    async def test_emit_skips_when_url_empty(self):
        """Empty URL means no HTTP calls even if enabled."""
        client = NotificationHubClient(
            url="", api_key="test-key", enabled=True,
        )

        with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
            await client.emit("appointment.booked", {"booking_id": "000"})

            mock_cls.assert_not_called()


class TestNotificationHubFireAndForget:
    """Tests that hub failures never propagate."""

    async def test_emit_swallows_connection_error(self):
        """Network failure is logged, not raised."""
        client = NotificationHubClient(
            url="http://hub.test", api_key="test-key", enabled=True,
        )

        with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(side_effect=ConnectionError("Hub is down"))

            # Must not raise
            await client.emit("appointment.booked", {"booking_id": "err"})

    async def test_emit_swallows_generic_exception(self):
        """Any exception is swallowed to protect booking operations."""
        client = NotificationHubClient(
            url="http://hub.test", api_key="test-key", enabled=True,
        )

        with patch("src.integrations.notification_hub.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(side_effect=RuntimeError("Unexpected"))

            # Must not raise
            await client.emit("appointment.cancelled", {"booking_id": "err2"})
