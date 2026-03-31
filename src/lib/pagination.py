"""Shared pagination utility for offset-based pagination.

Provides PaginationParams for use as a FastAPI dependency and constants
matching PRD §8b: default 25, max 100.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query

MAX_PAGE_SIZE: int = 100
DEFAULT_PAGE_SIZE: int = 25


@dataclass
class PaginationParams:
    """Validated, clamped pagination parameters.

    Use as a FastAPI dependency via ``Depends(PaginationParams)`` or
    construct directly for non-route contexts.
    """

    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        self.page = max(self.page, 1)
        self.page_size = max(min(self.page_size, MAX_PAGE_SIZE), 1)

    @property
    def offset(self) -> int:
        """SQL OFFSET derived from page and page_size."""
        return (self.page - 1) * self.page_size


def get_pagination(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
) -> PaginationParams:
    """FastAPI dependency that returns validated pagination params."""
    return PaginationParams(page=page, page_size=page_size)
