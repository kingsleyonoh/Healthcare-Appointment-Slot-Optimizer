"""Unit tests for src.optimizer.constraints — pure constraint helpers.

Tests cover: availability filtering, booking subtraction, buffer application,
room matching, room availability checking, and max daily enforcement.
"""

from datetime import date, time
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# get_availability_windows
# ---------------------------------------------------------------------------

class TestGetAvailabilityWindows:
    """Filter provider availability rows by day-of-week and validity range."""

    def test_filters_by_day_of_week(self):
        """Only rows matching the target date's weekday are returned."""
        from src.optimizer.constraints import get_availability_windows

        # Monday = weekday 0
        target = date(2026, 3, 23)  # Monday
        rows = [
            _avail_row(day_of_week=0, start=time(9, 0), end=time(17, 0)),
            _avail_row(day_of_week=2, start=time(8, 0), end=time(12, 0)),
        ]
        result = get_availability_windows(rows, target)
        assert len(result) == 1
        assert result[0] == (time(9, 0), time(17, 0))

    def test_respects_valid_from(self):
        """Rows with valid_from after target date are excluded."""
        from src.optimizer.constraints import get_availability_windows

        target = date(2026, 3, 23)  # Monday
        rows = [
            _avail_row(
                day_of_week=0,
                start=time(9, 0),
                end=time(17, 0),
                valid_from=date(2026, 4, 1),
            ),
        ]
        result = get_availability_windows(rows, target)
        assert result == []

    def test_respects_valid_until(self):
        """Rows with valid_until before target date are excluded."""
        from src.optimizer.constraints import get_availability_windows

        target = date(2026, 3, 23)
        rows = [
            _avail_row(
                day_of_week=0,
                start=time(9, 0),
                end=time(17, 0),
                valid_until=date(2026, 3, 20),
            ),
        ]
        result = get_availability_windows(rows, target)
        assert result == []

    def test_includes_row_on_boundary_dates(self):
        """Row is included when target equals valid_from or valid_until."""
        from src.optimizer.constraints import get_availability_windows

        target = date(2026, 3, 23)
        rows = [
            _avail_row(
                day_of_week=0,
                start=time(9, 0),
                end=time(12, 0),
                valid_from=date(2026, 3, 23),
                valid_until=date(2026, 3, 23),
            ),
        ]
        result = get_availability_windows(rows, target)
        assert len(result) == 1

    def test_returns_empty_when_no_match(self):
        """Empty list when no rows match the target day."""
        from src.optimizer.constraints import get_availability_windows

        target = date(2026, 3, 25)  # Wednesday = weekday 2
        rows = [
            _avail_row(day_of_week=0, start=time(9, 0), end=time(17, 0)),
        ]
        result = get_availability_windows(rows, target)
        assert result == []


# ---------------------------------------------------------------------------
# subtract_bookings
# ---------------------------------------------------------------------------

class TestSubtractBookings:
    """Subtract booked intervals from open windows."""

    def test_single_booking_in_middle(self):
        """A mid-day booking splits the window into two intervals."""
        from src.optimizer.constraints import subtract_bookings

        windows = [(time(9, 0), time(17, 0))]
        bookings = [_booking_row(start=time(12, 0), end=time(13, 0))]
        result = subtract_bookings(windows, bookings)
        assert result == [(time(9, 0), time(12, 0)), (time(13, 0), time(17, 0))]

    def test_multiple_bookings(self):
        """Multiple bookings carve multiple gaps."""
        from src.optimizer.constraints import subtract_bookings

        windows = [(time(9, 0), time(17, 0))]
        bookings = [
            _booking_row(start=time(10, 0), end=time(11, 0)),
            _booking_row(start=time(14, 0), end=time(15, 0)),
        ]
        result = subtract_bookings(windows, bookings)
        assert (time(9, 0), time(10, 0)) in result
        assert (time(11, 0), time(14, 0)) in result
        assert (time(15, 0), time(17, 0)) in result

    def test_no_bookings_returns_original(self):
        """Without bookings the windows are returned unchanged."""
        from src.optimizer.constraints import subtract_bookings

        windows = [(time(9, 0), time(12, 0))]
        result = subtract_bookings(windows, [])
        assert result == [(time(9, 0), time(12, 0))]

    def test_fully_booked_returns_empty(self):
        """If bookings cover the full window, nothing remains."""
        from src.optimizer.constraints import subtract_bookings

        windows = [(time(9, 0), time(12, 0))]
        bookings = [_booking_row(start=time(9, 0), end=time(12, 0))]
        result = subtract_bookings(windows, [])
        # With a booking covering the full window:
        result = subtract_bookings(windows, bookings)
        assert result == []


# ---------------------------------------------------------------------------
# apply_buffer
# ---------------------------------------------------------------------------

class TestApplyBuffer:
    """Apply buffer time between appointments by shrinking intervals."""

    def test_shrinks_interval_by_buffer(self):
        """Each interval's end is reduced by buffer_minutes."""
        from src.optimizer.constraints import apply_buffer

        windows = [(time(9, 0), time(12, 0))]
        result = apply_buffer(windows, buffer_minutes=10)
        assert result == [(time(9, 0), time(11, 50))]

    def test_zero_buffer_unchanged(self):
        """Zero buffer returns intervals unchanged."""
        from src.optimizer.constraints import apply_buffer

        windows = [(time(9, 0), time(12, 0))]
        result = apply_buffer(windows, buffer_minutes=0)
        assert result == [(time(9, 0), time(12, 0))]

    def test_buffer_eliminates_short_interval(self):
        """If buffer reduces interval to zero or negative, interval is dropped."""
        from src.optimizer.constraints import apply_buffer

        windows = [(time(9, 0), time(9, 5))]
        result = apply_buffer(windows, buffer_minutes=10)
        assert result == []


# ---------------------------------------------------------------------------
# filter_compatible_rooms
# ---------------------------------------------------------------------------

class TestFilterCompatibleRooms:
    """Filter rooms by type and equipment requirements."""

    def test_matches_room_type(self):
        """Rooms with correct type are included."""
        from src.optimizer.constraints import filter_compatible_rooms

        rooms = [
            _room_row(name="Exam-1", room_type="exam", equipment=["ecg"]),
            _room_row(name="Gen-1", room_type="general", equipment=[]),
        ]
        result = filter_compatible_rooms(rooms, "exam", [])
        assert len(result) == 1
        assert result[0].name == "Exam-1"

    def test_requires_equipment_subset(self):
        """Room must have all required equipment."""
        from src.optimizer.constraints import filter_compatible_rooms

        rooms = [
            _room_row(name="Exam-A", room_type="exam", equipment=["ecg"]),
            _room_row(name="Exam-B", room_type="exam", equipment=["ecg", "ultrasound"]),
        ]
        result = filter_compatible_rooms(rooms, "exam", ["ecg", "ultrasound"])
        assert len(result) == 1
        assert result[0].name == "Exam-B"

    def test_no_equipment_required(self):
        """When no equipment required, all matching-type rooms pass."""
        from src.optimizer.constraints import filter_compatible_rooms

        rooms = [
            _room_row(name="Gen-1", room_type="general", equipment=[]),
            _room_row(name="Gen-2", room_type="general", equipment=["scale"]),
        ]
        result = filter_compatible_rooms(rooms, "general", [])
        assert len(result) == 2

    def test_no_matching_rooms(self):
        """Returns empty when no rooms match."""
        from src.optimizer.constraints import filter_compatible_rooms

        rooms = [_room_row(name="Lab-1", room_type="lab", equipment=[])]
        result = filter_compatible_rooms(rooms, "exam", [])
        assert result == []


# ---------------------------------------------------------------------------
# check_room_availability
# ---------------------------------------------------------------------------

class TestCheckRoomAvailability:
    """Check free intervals for a specific room on a date."""

    def test_returns_full_window_when_no_bookings(self):
        """Without bookings the entire window is free."""
        from src.optimizer.constraints import check_room_availability

        window = (time(9, 0), time(17, 0))
        result = check_room_availability(window, [])
        assert result == [(time(9, 0), time(17, 0))]

    def test_subtracts_room_bookings(self):
        """Existing room bookings carve out used intervals."""
        from src.optimizer.constraints import check_room_availability

        window = (time(9, 0), time(17, 0))
        bookings = [_booking_row(start=time(10, 0), end=time(11, 0))]
        result = check_room_availability(window, bookings)
        assert (time(9, 0), time(10, 0)) in result
        assert (time(11, 0), time(17, 0)) in result


# ---------------------------------------------------------------------------
# check_max_daily
# ---------------------------------------------------------------------------

class TestCheckMaxDaily:
    """Check whether provider has reached max daily appointments."""

    def test_below_limit_returns_false(self):
        """Not at limit → False (not maxed out)."""
        from src.optimizer.constraints import check_max_daily

        assert check_max_daily(booking_count=5, max_daily=20) is False

    def test_at_limit_returns_true(self):
        """At exact limit → True (maxed out)."""
        from src.optimizer.constraints import check_max_daily

        assert check_max_daily(booking_count=20, max_daily=20) is True

    def test_over_limit_returns_true(self):
        """Over limit → True."""
        from src.optimizer.constraints import check_max_daily

        assert check_max_daily(booking_count=25, max_daily=20) is True


# ---------------------------------------------------------------------------
# Test helpers: lightweight fake row objects
# ---------------------------------------------------------------------------

def _avail_row(
    day_of_week: int,
    start: time,
    end: time,
    valid_from: date | None = None,
    valid_until: date | None = None,
) -> MagicMock:
    """Create a fake ProviderAvailability-like object."""
    row = MagicMock()
    row.day_of_week = day_of_week
    row.start_time = start
    row.end_time = end
    row.valid_from = valid_from or date(2000, 1, 1)
    row.valid_until = valid_until or date(2099, 12, 31)
    return row


def _booking_row(start: time, end: time) -> MagicMock:
    """Create a fake Booking-like object with start_time and end_time."""
    row = MagicMock()
    row.start_time = start
    row.end_time = end
    return row


def _room_row(name: str, room_type: str, equipment: list[str]) -> MagicMock:
    """Create a fake Room-like object."""
    row = MagicMock()
    row.name = name
    row.room_type = room_type
    row.equipment = equipment
    row.enabled = True
    return row
