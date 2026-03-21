"""Time interval math for slot computation.

All functions work with ``datetime.time`` objects representing clock
times within a single day.  No date arithmetic is needed.
"""

from __future__ import annotations

from datetime import time, timedelta


def time_to_minutes(t: time) -> int:
    """Convert a ``time`` to minutes since midnight."""
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> time:
    """Convert minutes since midnight back to a ``time``."""
    return time(m // 60, m % 60)


def subtract_interval(
    window: tuple[time, time],
    booked: tuple[time, time],
) -> list[tuple[time, time]]:
    """Remove *booked* from *window*, returning remaining intervals.

    Returns a list of 0–2 ``(start, end)`` tuples.
    """
    ws, we = time_to_minutes(window[0]), time_to_minutes(window[1])
    bs, be = time_to_minutes(booked[0]), time_to_minutes(booked[1])

    # No overlap
    if be <= ws or bs >= we:
        return [window]

    result: list[tuple[time, time]] = []
    if bs > ws:
        result.append((_minutes_to_time(ws), _minutes_to_time(bs)))
    if be < we:
        result.append((_minutes_to_time(be), _minutes_to_time(we)))
    return result


def generate_slots(
    start: time,
    end: time,
    duration_minutes: int,
    increment_minutes: int = 15,
    buffer_minutes: int = 0,
) -> list[tuple[time, time]]:
    """Generate candidate slots within an open window.

    Each slot is ``(slot_start, slot_end)`` where the slot fits entirely
    within ``[start, end]`` and accounts for post-appointment buffer.

    Args:
        start: Window open time.
        end: Window close time.
        duration_minutes: Appointment length in minutes.
        increment_minutes: Time between slot starts (default 15).
        buffer_minutes: Required buffer after each appointment.

    Returns:
        List of ``(start, end)`` time pairs.
    """
    s = time_to_minutes(start)
    e = time_to_minutes(end)
    effective = duration_minutes + buffer_minutes
    slots: list[tuple[time, time]] = []

    cursor = s
    while cursor + duration_minutes <= e:
        # The slot itself must fit; buffer is advisory (shouldn't exceed window)
        if cursor + effective <= e or cursor + duration_minutes <= e:
            slot_end = cursor + duration_minutes
            if slot_end <= e:
                slots.append((_minutes_to_time(cursor), _minutes_to_time(slot_end)))
        cursor += increment_minutes

    # Apply buffer constraint: remove slots where start + effective > end
    if buffer_minutes:
        slots = [
            (ss, se)
            for ss, se in slots
            if time_to_minutes(ss) + effective <= e
        ]

    return slots
