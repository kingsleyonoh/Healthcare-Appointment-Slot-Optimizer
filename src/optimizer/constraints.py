"""Constraint evaluation helpers for the Slot Optimizer.

Pure functions — no database access. Receive pre-loaded rows and compute
availability windows, apply buffers, filter rooms, and enforce limits.
"""

from __future__ import annotations

from datetime import date, time, timedelta

from src.lib.time_utils import subtract_interval, time_to_minutes


def get_availability_windows(
    availability_rows: list,
    target_date: date,
) -> list[tuple[time, time]]:
    """Return (start, end) windows for rows matching target date.

    Filters by day_of_week matching ``target_date.weekday()`` and
    checks that ``valid_from <= target_date <= valid_until``.
    """
    weekday = target_date.weekday()
    windows: list[tuple[time, time]] = []
    for row in availability_rows:
        if row.day_of_week != weekday:
            continue
        if row.valid_from and target_date < row.valid_from:
            continue
        if row.valid_until and target_date > row.valid_until:
            continue
        windows.append((row.start_time, row.end_time))
    return windows


def subtract_bookings(
    windows: list[tuple[time, time]],
    bookings: list,
) -> list[tuple[time, time]]:
    """Remove booked intervals from availability windows.

    Uses ``time_utils.subtract_interval`` to carve each booking out of
    every window, producing the remaining open intervals.
    """
    result = list(windows)
    for booking in bookings:
        booked = (booking.start_time, booking.end_time)
        new_result: list[tuple[time, time]] = []
        for window in result:
            new_result.extend(subtract_interval(window, booked))
        result = new_result
    return result


def apply_buffer(
    windows: list[tuple[time, time]],
    buffer_minutes: int,
) -> list[tuple[time, time]]:
    """Shrink each window's end by *buffer_minutes*.

    Intervals that become zero-length or negative are dropped.
    """
    if buffer_minutes <= 0:
        return list(windows)

    result: list[tuple[time, time]] = []
    for start, end in windows:
        end_mins = time_to_minutes(end) - buffer_minutes
        start_mins = time_to_minutes(start)
        if end_mins > start_mins:
            new_end = _minutes_to_time(end_mins)
            result.append((start, new_end))
    return result


def filter_compatible_rooms(
    rooms: list,
    required_type: str,
    required_equipment: list[str],
) -> list:
    """Return rooms matching *required_type* with all *required_equipment*."""
    equipment_set = set(required_equipment)
    return [
        r
        for r in rooms
        if r.room_type == required_type
        and equipment_set.issubset(set(r.equipment))
    ]


def check_room_availability(
    window: tuple[time, time],
    bookings: list,
) -> list[tuple[time, time]]:
    """Return free intervals within *window* after subtracting *bookings*."""
    return subtract_bookings([window], bookings)


def check_max_daily(booking_count: int, max_daily: int) -> bool:
    """Return ``True`` if provider has reached or exceeded *max_daily*."""
    return booking_count >= max_daily


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _minutes_to_time(minutes: int) -> time:
    """Convert minutes-since-midnight back to a ``time`` object."""
    hours = minutes // 60
    mins = minutes % 60
    return time(hours, mins)
