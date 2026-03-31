"""Unit tests for src.optimizer.scorer — slot quality scoring.

Tests cover: preference matching, gap minimization, room switching penalty,
overbooking penalty, and combined score calculation.
"""

from datetime import time

import pytest


# ---------------------------------------------------------------------------
# score_preference_match
# ---------------------------------------------------------------------------

class TestScorePreferenceMatch:
    """Score how close a slot is to the patient's preferred time."""

    def test_exact_match_returns_max_score(self):
        """Slot starting at preferred time scores 1.0."""
        from src.optimizer.scorer import score_preference_match

        result = score_preference_match(
            slot_start=time(10, 0),
            preferred_start=time(10, 0),
            preferred_end=time(12, 0),
        )
        assert result == 1.0

    def test_within_window_returns_high_score(self):
        """Slot within the preferred window scores 1.0."""
        from src.optimizer.scorer import score_preference_match

        result = score_preference_match(
            slot_start=time(11, 0),
            preferred_start=time(10, 0),
            preferred_end=time(12, 0),
        )
        assert result == 1.0

    def test_outside_window_returns_lower_score(self):
        """Slot outside the preferred window scores less than 1.0."""
        from src.optimizer.scorer import score_preference_match

        result = score_preference_match(
            slot_start=time(14, 0),
            preferred_start=time(10, 0),
            preferred_end=time(12, 0),
        )
        assert result < 1.0

    def test_no_preference_returns_neutral(self):
        """No preference provided returns 0.5 (neutral)."""
        from src.optimizer.scorer import score_preference_match

        result = score_preference_match(
            slot_start=time(10, 0),
            preferred_start=None,
            preferred_end=None,
        )
        assert result == 0.5

    def test_far_from_preference_scores_near_zero(self):
        """Slot very far from preference scores near 0."""
        from src.optimizer.scorer import score_preference_match

        result = score_preference_match(
            slot_start=time(8, 0),
            preferred_start=time(16, 0),
            preferred_end=time(17, 0),
        )
        assert result < 0.3


# ---------------------------------------------------------------------------
# score_gap_minimization
# ---------------------------------------------------------------------------

class TestScoreGapMinimization:
    """Score based on minimizing gaps in the provider's day."""

    def test_no_gap_scores_high(self):
        """Slot adjacent to existing booking scores 1.0."""
        from src.optimizer.scorer import score_gap_minimization

        existing_bookings = [
            _booking(start=time(9, 0), end=time(10, 0)),
        ]
        result = score_gap_minimization(
            slot_start=time(10, 0),
            provider_bookings=existing_bookings,
        )
        assert result == 1.0

    def test_small_gap_scores_medium(self):
        """Slot with 30-min gap from nearest booking scores moderately."""
        from src.optimizer.scorer import score_gap_minimization

        existing_bookings = [
            _booking(start=time(9, 0), end=time(10, 0)),
        ]
        result = score_gap_minimization(
            slot_start=time(10, 30),
            provider_bookings=existing_bookings,
        )
        assert 0.3 < result < 1.0

    def test_no_existing_bookings_returns_neutral(self):
        """No existing bookings → neutral score."""
        from src.optimizer.scorer import score_gap_minimization

        result = score_gap_minimization(
            slot_start=time(10, 0),
            provider_bookings=[],
        )
        assert result == 0.5

    def test_large_gap_scores_low(self):
        """Slot with large gap from any booking scores low."""
        from src.optimizer.scorer import score_gap_minimization

        existing_bookings = [
            _booking(start=time(9, 0), end=time(9, 30)),
        ]
        result = score_gap_minimization(
            slot_start=time(15, 0),
            provider_bookings=existing_bookings,
        )
        assert result < 0.5


# ---------------------------------------------------------------------------
# score_room_switching
# ---------------------------------------------------------------------------

class TestScoreRoomSwitching:
    """Penalize when provider must switch rooms."""

    def test_same_room_scores_high(self):
        """Provider staying in same room scores 1.0."""
        from src.optimizer.scorer import score_room_switching

        result = score_room_switching(
            room_id="room-1",
            provider_rooms_used=["room-1"],
        )
        assert result == 1.0

    def test_different_room_scores_lower(self):
        """Provider switching rooms scores less than 1.0."""
        from src.optimizer.scorer import score_room_switching

        result = score_room_switching(
            room_id="room-2",
            provider_rooms_used=["room-1"],
        )
        assert result < 1.0

    def test_no_rooms_used_returns_neutral(self):
        """No prior rooms → neutral score."""
        from src.optimizer.scorer import score_room_switching

        result = score_room_switching(
            room_id="room-1",
            provider_rooms_used=[],
        )
        assert result == 0.5


# ---------------------------------------------------------------------------
# score_slot (combined)
# ---------------------------------------------------------------------------

class TestScoreSlot:
    """Combined quality score from all components."""

    def test_perfect_slot_scores_near_one(self):
        """Optimal slot with all factors aligned scores close to 1.0."""
        from src.optimizer.scorer import score_slot

        result = score_slot(
            slot_start=time(10, 0),
            slot_end=time(10, 30),
            provider_bookings=[_booking(start=time(9, 0), end=time(10, 0))],
            preferred_start=time(10, 0),
            preferred_end=time(12, 0),
            provider_rooms_used=["room-1"],
            room_id="room-1",
            is_overbooked=False,
        )
        assert result > 0.8

    def test_overbooked_slot_scores_lower(self):
        """Overbooked slot should score lower than equivalent non-overbooked."""
        from src.optimizer.scorer import score_slot

        base = score_slot(
            slot_start=time(10, 0),
            slot_end=time(10, 30),
            provider_bookings=[],
            preferred_start=None,
            preferred_end=None,
            provider_rooms_used=[],
            room_id="room-1",
            is_overbooked=False,
        )
        overbooked = score_slot(
            slot_start=time(10, 0),
            slot_end=time(10, 30),
            provider_bookings=[],
            preferred_start=None,
            preferred_end=None,
            provider_rooms_used=[],
            room_id="room-1",
            is_overbooked=True,
        )
        assert overbooked < base

    def test_score_always_between_zero_and_one(self):
        """Score is always in [0.0, 1.0] range."""
        from src.optimizer.scorer import score_slot

        result = score_slot(
            slot_start=time(8, 0),
            slot_end=time(8, 30),
            provider_bookings=[],
            preferred_start=time(16, 0),
            preferred_end=time(17, 0),
            provider_rooms_used=["room-x"],
            room_id="room-y",
            is_overbooked=True,
        )
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _booking:
    """Lightweight booking-like object for tests."""

    def __init__(self, start: time, end: time, room_id: str = "room-1"):
        self.start_time = start
        self.end_time = end
        self.room_id = room_id
