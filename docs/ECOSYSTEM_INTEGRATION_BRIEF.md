# Ecosystem Integration Brief — Healthcare → Notification Hub

> **Purpose:** Wire the Healthcare Appointment Slot Optimizer to the Event-Driven Notification Hub.
> This is the first domain service consuming the backbone. It proves the ecosystem works end-to-end.

---

## What Needs to Happen

When a booking is **created**, **cancelled**, or a patient **no-shows**, emit an event to the Notification Hub so it can route notifications (email confirmations, SMS reminders, in-app alerts) to patients and staff.

---

## Integration Method: HTTP API (not Kafka directly)

The Hub exposes `POST /api/events` — a REST endpoint that accepts events over HTTP and publishes them to Kafka internally. **The Healthcare app does NOT need a Kafka producer.** One HTTP call per event.

### Endpoint

```
POST {NOTIFICATION_HUB_URL}/api/events
```

### Authentication

```
Header: X-API-Key: {NOTIFICATION_HUB_API_KEY}
```

The API key maps to a tenant. The Hub resolves `tenant_id` from the key automatically — you never send `tenant_id` in the body.

### Request Body

```json
{
  "event_type": "appointment.booked",
  "event_id": "unique-idempotency-key",
  "payload": {
    "appointment_id": "uuid",
    "patient_name": "Jane Doe",
    "patient_email": "jane@example.com",
    "provider_name": "Dr. Smith",
    "provider_email": "smith@clinic.com",
    "room_name": "Room 4A",
    "appointment_type": "General Checkup",
    "start_time": "2026-03-25T14:00:00Z",
    "end_time": "2026-03-25T14:30:00Z",
    "clinic_name": "Metro Health Clinic"
  }
}
```

### Response

```json
{ "published": true }
```

### Rate Limit

**10 requests/minute** per tenant. Sufficient for booking operations.

---

## Events to Emit

| Event Type | When | Key Payload Fields |
|------------|------|--------------------|
| `appointment.booked` | Booking created successfully | `appointment_id`, `patient_email`, `patient_name`, `provider_name`, `start_time`, `end_time`, `appointment_type`, `room_name` |
| `appointment.cancelled` | Booking cancelled | `appointment_id`, `patient_email`, `patient_name`, `provider_name`, `start_time`, `reason` |
| `appointment.no_show` | Patient marked no-show | `appointment_id`, `patient_email`, `patient_name`, `provider_name`, `start_time` |

### Event ID (Idempotency Key)

Use `f"{event_type}:{appointment_id}:{timestamp_iso}"` to prevent duplicate notifications. The Hub deduplicates on `event_id + recipient + channel` within a configurable window (default 60 min).

---

## Implementation Guide

### 1. Add Environment Variables

```env
# .env
NOTIFICATION_HUB_URL=http://notifications.kingsleyonoh.com
NOTIFICATION_HUB_API_KEY=healthcare-tenant-api-key
NOTIFICATION_HUB_ENABLED=true
```

Use `NOTIFICATION_HUB_ENABLED` as a feature flag — when `false`, skip the HTTP call. This lets you develop without the Hub running.

### 2. Create a Notification Client (Python)

```python
# src/integrations/notification_hub.py

import httpx
import logging
from datetime import datetime, timezone

from src.core.config import settings

logger = logging.getLogger(__name__)


class NotificationHubClient:
    """HTTP client for the Event-Driven Notification Hub."""

    def __init__(self):
        self.base_url = settings.NOTIFICATION_HUB_URL
        self.api_key = settings.NOTIFICATION_HUB_API_KEY
        self.enabled = settings.NOTIFICATION_HUB_ENABLED

    async def emit_event(
        self,
        event_type: str,
        appointment_id: str,
        payload: dict,
    ) -> bool:
        """Emit a domain event to the Notification Hub.

        Returns True if published, False if skipped or failed.
        Fire-and-forget — booking operations must NOT fail
        because the Hub is down.
        """
        if not self.enabled:
            logger.debug("Notification Hub disabled, skipping event: %s", event_type)
            return False

        event_id = f"{event_type}:{appointment_id}:{datetime.now(timezone.utc).isoformat()}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/events",
                    json={
                        "event_type": event_type,
                        "event_id": event_id,
                        "payload": payload,
                    },
                    headers={"X-API-Key": self.api_key},
                )
                response.raise_for_status()
                logger.info("Event published: %s for appointment %s", event_type, appointment_id)
                return True
        except httpx.HTTPStatusError as e:
            logger.error("Hub rejected event %s: %s %s", event_type, e.response.status_code, e.response.text)
            return False
        except httpx.RequestError as e:
            logger.warning("Hub unreachable for event %s: %s", event_type, str(e))
            return False


# Singleton
notification_hub = NotificationHubClient()
```

### 3. Emit Events from the Booking Service (Phase 4)

```python
# In your booking creation endpoint / service layer

from src.integrations.notification_hub import notification_hub

async def create_booking(booking_data: BookingCreate, db: AsyncSession):
    # ... existing booking creation logic ...
    booking = await booking_repo.create(db, booking_data)

    # Fire-and-forget — don't await in the request path if latency matters
    await notification_hub.emit_event(
        event_type="appointment.booked",
        appointment_id=str(booking.id),
        payload={
            "appointment_id": str(booking.id),
            "patient_name": booking.patient_name,
            "patient_email": booking.patient_email,
            "provider_name": booking.provider.name,
            "provider_email": booking.provider.email,
            "room_name": booking.room.name,
            "appointment_type": booking.appointment_type.name,
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
        },
    )

    return booking
```

### 4. Add Config Settings

```python
# In src/core/config.py — add to your Settings class

class Settings(BaseSettings):
    # ... existing settings ...

    # Notification Hub integration
    NOTIFICATION_HUB_URL: str = ""
    NOTIFICATION_HUB_API_KEY: str = ""
    NOTIFICATION_HUB_ENABLED: bool = False  # Off by default
```

### 5. Testing

```python
# tests/unit/test_notification_hub.py

import pytest
from unittest.mock import AsyncMock, patch

from src.integrations.notification_hub import NotificationHubClient


@pytest.fixture
def hub_client():
    client = NotificationHubClient()
    client.enabled = True
    client.base_url = "http://localhost:3000"
    client.api_key = "test-key"
    return client


async def test_emit_event_disabled(hub_client):
    hub_client.enabled = False
    result = await hub_client.emit_event("appointment.booked", "123", {"test": True})
    assert result is False


async def test_emit_event_success(hub_client):
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(status_code=200, json=lambda: {"published": True})
        mock_post.return_value.raise_for_status = lambda: None
        result = await hub_client.emit_event("appointment.booked", "123", {"test": True})
        assert result is True


async def test_emit_event_hub_down(hub_client):
    """Booking must NOT fail when Hub is unreachable."""
    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
        result = await hub_client.emit_event("appointment.booked", "123", {"test": True})
        assert result is False
```

---

## PRD Updates Required

### Section 6b: Ecosystem Integration Points (NEW)

Add this section after Section 6 (Connectors/Integrations):

```markdown
## 6b. Ecosystem Integration Points

| Target Service | Direction | Protocol | Purpose |
|---------------|-----------|----------|---------|
| Event-Driven Notification Hub | Outbound | HTTP REST | Emit appointment lifecycle events for notification routing |

### Integration Details

- **Endpoint:** `POST {NOTIFICATION_HUB_URL}/api/events`
- **Auth:** API key in `X-API-Key` header (tenant-scoped)
- **Events emitted:** `appointment.booked`, `appointment.cancelled`, `appointment.no_show`
- **Failure mode:** Fire-and-forget. Hub downtime does NOT affect booking operations.
- **Feature flag:** `NOTIFICATION_HUB_ENABLED` (default: false)
```

### Section 14: Environment Variables (ADD)

```
NOTIFICATION_HUB_URL          — Base URL of the Notification Hub (e.g., http://notifications.kingsleyonoh.com)
NOTIFICATION_HUB_API_KEY      — Tenant API key issued by the Hub
NOTIFICATION_HUB_ENABLED      — Feature flag to enable/disable event emission (default: false)
```

### progress.md Updates

Add to Phase 4 (Booking Engine) or create a Phase 4b:

```markdown
### Notification Hub Integration
- [ ] 4.X.1 Create `src/integrations/notification_hub.py` with async HTTP client
- [ ] 4.X.2 Add Hub env vars to `Settings` class
- [ ] 4.X.3 Emit `appointment.booked` event from booking creation
- [ ] 4.X.4 Emit `appointment.cancelled` event from booking cancellation
- [ ] 4.X.5 Emit `appointment.no_show` event from no-show marking
- [ ] 4.X.6 Unit tests for NotificationHubClient (enabled/disabled/failure)
- [ ] 4.X.7 Integration test: verify event payload shape matches Hub contract
```

---

## Hub-Side Setup (One-Time)

When the Hub is deployed, register the Healthcare tenant:

```sql
INSERT INTO tenants (id, name, api_key) 
VALUES ('healthcare', 'Healthcare Appointment Optimizer', 'healthcare-api-key-generate-real-one');
```

Then create rules and templates via the Hub's API:

```bash
# Example: appointment booked → email patient
curl -X POST http://notifications.kingsleyonoh.com/api/rules \
  -H "X-API-Key: healthcare-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "appointment.booked",
    "channel": "email",
    "template_id": "<template-uuid>",
    "recipient_type": "event_field",
    "recipient_value": "patient_email",
    "urgency": "normal"
  }'
```

---

## Dependency

```
Healthcare Appointment Slot Optimizer
  └── depends on → Event-Driven Notification Hub (for notification delivery)
       └── must be deployed and tenant configured before enabling integration
```

This is a **soft dependency** — the feature flag (`NOTIFICATION_HUB_ENABLED=false`) means the app works standalone. Enable when Hub is live.
