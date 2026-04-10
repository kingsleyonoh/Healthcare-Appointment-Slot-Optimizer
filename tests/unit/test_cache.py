"""Unit tests for in-memory availability cache.

Tests TTL expiry, invalidation on update, and cache hit/miss behavior.
"""

from __future__ import annotations

import time as _time

import pytest

from src.lib.cache import AvailabilityCache


class TestCacheHitMiss:
    """Tests for basic cache get/set behavior."""

    def test_get_returns_none_on_miss(self):
        """Cache miss returns None."""
        cache = AvailabilityCache(ttl_seconds=60)
        assert cache.get("nonexistent") is None

    def test_set_and_get_returns_cached_value(self):
        """Value set in cache is retrievable."""
        cache = AvailabilityCache(ttl_seconds=60)
        data = [("09:00", "12:00"), ("13:00", "17:00")]
        cache.set("provider-1", data)

        result = cache.get("provider-1")
        assert result == data

    def test_different_keys_are_independent(self):
        """Each key stores its own value."""
        cache = AvailabilityCache(ttl_seconds=60)
        cache.set("provider-1", [("09:00", "12:00")])
        cache.set("provider-2", [("10:00", "14:00")])

        assert cache.get("provider-1") == [("09:00", "12:00")]
        assert cache.get("provider-2") == [("10:00", "14:00")]


class TestCacheTTL:
    """Tests for TTL-based expiry."""

    def test_expired_entry_returns_none(self):
        """After TTL expires, cache returns None."""
        cache = AvailabilityCache(ttl_seconds=0.1)  # 100ms TTL
        cache.set("provider-1", [("09:00", "12:00")])

        _time.sleep(0.15)  # Wait for TTL

        assert cache.get("provider-1") is None

    def test_non_expired_entry_returns_value(self):
        """Before TTL expires, cache returns the value."""
        cache = AvailabilityCache(ttl_seconds=60)
        cache.set("provider-1", [("09:00", "12:00")])

        result = cache.get("provider-1")
        assert result == [("09:00", "12:00")]


class TestCacheInvalidation:
    """Tests for explicit cache invalidation."""

    def test_invalidate_removes_specific_key(self):
        """Invalidating a key removes only that key."""
        cache = AvailabilityCache(ttl_seconds=60)
        cache.set("provider-1", [("09:00", "12:00")])
        cache.set("provider-2", [("10:00", "14:00")])

        cache.invalidate("provider-1")

        assert cache.get("provider-1") is None
        assert cache.get("provider-2") == [("10:00", "14:00")]

    def test_invalidate_all_clears_entire_cache(self):
        """invalidate_all() clears all entries."""
        cache = AvailabilityCache(ttl_seconds=60)
        cache.set("provider-1", [("09:00", "12:00")])
        cache.set("provider-2", [("10:00", "14:00")])

        cache.invalidate_all()

        assert cache.get("provider-1") is None
        assert cache.get("provider-2") is None

    def test_invalidate_nonexistent_key_does_not_error(self):
        """Invalidating a missing key is a no-op."""
        cache = AvailabilityCache(ttl_seconds=60)
        cache.invalidate("nonexistent")  # Should not raise

    def test_set_overwrites_existing_value(self):
        """Setting a key that exists overwrites with new TTL."""
        cache = AvailabilityCache(ttl_seconds=60)
        cache.set("provider-1", [("09:00", "12:00")])
        cache.set("provider-1", [("10:00", "15:00")])

        assert cache.get("provider-1") == [("10:00", "15:00")]
