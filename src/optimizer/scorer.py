"""Slot quality scoring for the Slot Optimizer.

Pure functions that evaluate candidate slots and return scores in [0.0, 1.0].
Higher scores indicate more desirable slots.

Scoring weights (per PRD §5.1):
- Preference match: 40%
- Gap minimization: 35%
- Room switching penalty: 15%
- Overbooking penalty: 10%
"""

from __future__ import annotations

from datetime import time

from src.lib.time_utils import time_to_minutes

# Scoring weights
_W_PREFERENCE = 0.40
_W_GAP = 0.35
_W_ROOM = 0.15
_W_OVERBOOK = 0.10

# Maximum gap (minutes) used for normalisation
_MAX_GAP_MINUTES = 480  # 8 hours


def score_preference_match(
    slot_start: time,
    preferred_start: time | None,
    preferred_end: time | None,
) -> float:
    """Score proximity to patient's preferred time window.

    Returns 1.0 if slot falls within the window, decays linearly
    with distance.  Returns 0.5 (neutral) when no preference given.
    """
    if preferred_start is None or preferred_end is None:
        return 0.5

    slot_mins = time_to_minutes(slot_start)
    pref_start_mins = time_to_minutes(preferred_start)
    pref_end_mins = time_to_minutes(preferred_end)

    if pref_start_mins <= slot_mins <= pref_end_mins:
        return 1.0

    # Distance from nearest edge of the preferred window
    distance = min(
        abs(slot_mins - pref_start_mins),
        abs(slot_mins - pref_end_mins),
    )
    # Decay: score drops to ~0 at 480 min away
    return max(0.0, 1.0 - distance / _MAX_GAP_MINUTES)


def score_gap_minimization(
    slot_start: time,
    provider_bookings: list,
) -> float:
    """Score based on how close the slot is to existing bookings.

    Adjacent slots (gap == 0) score 1.0.  Larger gaps decay toward 0.
    Returns 0.5 (neutral) when there are no existing bookings.
    """
    if not provider_bookings:
        return 0.5

    slot_mins = time_to_minutes(slot_start)
    min_gap = _MAX_GAP_MINUTES

    for booking in provider_bookings:
        end_mins = time_to_minutes(booking.end_time)
        start_mins = time_to_minutes(booking.start_time)
        # Gap to end of this booking or start of this booking
        gap = min(abs(slot_mins - end_mins), abs(slot_mins - start_mins))
        min_gap = min(min_gap, gap)

    if min_gap == 0:
        return 1.0
    return max(0.0, 1.0 - min_gap / _MAX_GAP_MINUTES)


def score_room_switching(
    room_id: str,
    provider_rooms_used: list[str],
) -> float:
    """Penalise room switches.

    Returns 1.0 if provider stays in a room they've already used,
    0.5 (neutral) if no rooms used yet, lower otherwise.
    """
    if not provider_rooms_used:
        return 0.5

    if str(room_id) in [str(r) for r in provider_rooms_used]:
        return 1.0
    return 0.3


def score_slot(
    slot_start: time,
    slot_end: time,
    provider_bookings: list,
    preferred_start: time | None,
    preferred_end: time | None,
    provider_rooms_used: list[str],
    room_id: str,
    is_overbooked: bool,
) -> float:
    """Compute combined quality score for a candidate slot.

    Returns a float in [0.0, 1.0] using weighted components.
    """
    pref = score_preference_match(slot_start, preferred_start, preferred_end)
    gap = score_gap_minimization(slot_start, provider_bookings)
    room = score_room_switching(room_id, provider_rooms_used)
    overbook = 0.0 if is_overbooked else 1.0

    raw = (
        _W_PREFERENCE * pref
        + _W_GAP * gap
        + _W_ROOM * room
        + _W_OVERBOOK * overbook
    )
    return round(min(1.0, max(0.0, raw)), 4)
