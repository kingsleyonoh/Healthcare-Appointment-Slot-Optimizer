"""Unit tests for the shared pagination utility."""

import pytest

from src.lib.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PaginationParams


class TestPaginationParams:
    """Tests for PaginationParams construction and offset calculation."""

    def test_defaults(self):
        """Default page=1, page_size=DEFAULT_PAGE_SIZE, offset=0."""
        p = PaginationParams()
        assert p.page == 1
        assert p.page_size == DEFAULT_PAGE_SIZE
        assert p.offset == 0

    def test_offset_page_one(self):
        """Page 1 always has offset 0."""
        p = PaginationParams(page=1, page_size=25)
        assert p.offset == 0

    def test_offset_page_three(self):
        """Page 3 with page_size=25 → offset=50."""
        p = PaginationParams(page=3, page_size=25)
        assert p.offset == 50

    def test_offset_page_two_size_ten(self):
        """Page 2 with page_size=10 → offset=10."""
        p = PaginationParams(page=2, page_size=10)
        assert p.offset == 10

    def test_max_page_size_cap(self):
        """page_size above MAX_PAGE_SIZE is capped."""
        p = PaginationParams(page=1, page_size=500)
        assert p.page_size == MAX_PAGE_SIZE

    def test_page_size_zero_clamps_to_one(self):
        """page_size=0 is clamped to 1."""
        p = PaginationParams(page=1, page_size=0)
        assert p.page_size == 1

    def test_page_size_negative_clamps_to_one(self):
        """Negative page_size is clamped to 1."""
        p = PaginationParams(page=1, page_size=-5)
        assert p.page_size == 1

    def test_page_zero_clamps_to_one(self):
        """page=0 is clamped to 1."""
        p = PaginationParams(page=0, page_size=25)
        assert p.page == 1
        assert p.offset == 0

    def test_page_negative_clamps_to_one(self):
        """Negative page is clamped to 1."""
        p = PaginationParams(page=-3, page_size=25)
        assert p.page == 1
        assert p.offset == 0

    def test_exact_max_page_size(self):
        """page_size=MAX_PAGE_SIZE is allowed (not capped)."""
        p = PaginationParams(page=1, page_size=MAX_PAGE_SIZE)
        assert p.page_size == MAX_PAGE_SIZE

    def test_large_page_number(self):
        """Large page numbers produce correct offset."""
        p = PaginationParams(page=100, page_size=25)
        assert p.offset == 2475  # (100-1) * 25

    def test_constants(self):
        """Verify constants match PRD spec."""
        assert DEFAULT_PAGE_SIZE == 25
        assert MAX_PAGE_SIZE == 100
