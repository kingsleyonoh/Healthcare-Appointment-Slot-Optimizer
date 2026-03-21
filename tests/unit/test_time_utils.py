"""Unit tests for src.lib.time_utils — time interval math."""

from datetime import time

import pytest


class TestSubtractInterval:
    """Test subtracting one time interval from another."""

    def test_no_overlap_returns_original(self):
        """Non-overlapping intervals should return the original unchanged."""
        from src.lib.time_utils import subtract_interval

        result = subtract_interval(
            (time(9, 0), time(12, 0)),
            (time(13, 0), time(14, 0)),
        )
        assert result == [(time(9, 0), time(12, 0))]

    def test_full_overlap_returns_empty(self):
        """If booked covers the entire window, result should be empty."""
        from src.lib.time_utils import subtract_interval

        result = subtract_interval(
            (time(9, 0), time(12, 0)),
            (time(9, 0), time(12, 0)),
        )
        assert result == []

    def test_partial_overlap_start(self):
        """Booking at the start should trim the beginning."""
        from src.lib.time_utils import subtract_interval

        result = subtract_interval(
            (time(9, 0), time(12, 0)),
            (time(9, 0), time(10, 0)),
        )
        assert result == [(time(10, 0), time(12, 0))]

    def test_partial_overlap_end(self):
        """Booking at the end should trim the tail."""
        from src.lib.time_utils import subtract_interval

        result = subtract_interval(
            (time(9, 0), time(12, 0)),
            (time(11, 0), time(12, 0)),
        )
        assert result == [(time(9, 0), time(11, 0))]

    def test_middle_overlap_splits(self):
        """Booking in the middle should split into two intervals."""
        from src.lib.time_utils import subtract_interval

        result = subtract_interval(
            (time(9, 0), time(17, 0)),
            (time(12, 0), time(13, 0)),
        )
        assert result == [(time(9, 0), time(12, 0)), (time(13, 0), time(17, 0))]


class TestGenerateSlots:
    """Test generating candidate time slots within an open window."""

    def test_basic_slot_generation(self):
        """Should generate 15-min slots within a window."""
        from src.lib.time_utils import generate_slots

        slots = generate_slots(
            start=time(9, 0),
            end=time(10, 0),
            duration_minutes=30,
            increment_minutes=15,
        )
        # 09:00-09:30, 09:15-09:45, 09:30-10:00
        assert len(slots) == 3
        assert slots[0] == (time(9, 0), time(9, 30))
        assert slots[-1] == (time(9, 30), time(10, 0))

    def test_no_slots_when_window_too_small(self):
        """Should return empty when window is smaller than duration."""
        from src.lib.time_utils import generate_slots

        slots = generate_slots(
            start=time(9, 0),
            end=time(9, 15),
            duration_minutes=30,
            increment_minutes=15,
        )
        assert slots == []

    def test_buffer_time_applied(self):
        """Buffer time should reduce the effective window for each slot."""
        from src.lib.time_utils import generate_slots

        slots = generate_slots(
            start=time(9, 0),
            end=time(10, 0),
            duration_minutes=30,
            increment_minutes=15,
            buffer_minutes=10,
        )
        # Each slot needs 30 + 10 = 40 min effective space
        # 09:00-09:30 (buffer to 09:40), 09:15-09:45 (buffer to 09:55)
        # 09:30-10:00 (buffer would go to 10:10 — exceeds end)
        # Actually: slot start + duration + buffer <= end
        # Only slots where start + 40 <= 60 → start <= 20 min past 9
        # 09:00 (OK), 09:15 (OK), 09:30 (9:30+40=10:10 > 10:00, skip)
        assert len(slots) == 2


class TestTimeToMinutes:
    """Test converting time objects to minutes since midnight."""

    def test_midnight(self):
        from src.lib.time_utils import time_to_minutes

        assert time_to_minutes(time(0, 0)) == 0

    def test_noon(self):
        from src.lib.time_utils import time_to_minutes

        assert time_to_minutes(time(12, 0)) == 720

    def test_with_minutes(self):
        from src.lib.time_utils import time_to_minutes

        assert time_to_minutes(time(9, 30)) == 570
