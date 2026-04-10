"""In-memory TTL cache for provider availability windows.

Simple thread-safe cache with per-entry TTL and explicit invalidation.
Suitable for single-process deployments. Replace with Redis for
multi-process / production if needed.
"""

from __future__ import annotations

import threading
import time as _time
from typing import Any


class AvailabilityCache:
    """In-memory cache with per-entry TTL.

    Parameters
    ----------
    ttl_seconds:
        Time-to-live for each cache entry in seconds. Default 60.
    """

    def __init__(self, *, ttl_seconds: float = 60.0) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """Return cached value or ``None`` if missing / expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if _time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        """Store a value with the configured TTL."""
        with self._lock:
            self._store[key] = (_time.monotonic() + self._ttl, value)

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        with self._lock:
            self._store.pop(key, None)

    def invalidate_all(self) -> None:
        """Clear the entire cache."""
        with self._lock:
            self._store.clear()
