"""APScheduler factory.

Provides ``create_scheduler()`` which returns a :class:`BackgroundScheduler`
ready to be started inside the FastAPI lifespan.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler


def create_scheduler() -> BackgroundScheduler:
    """Create a new ``BackgroundScheduler``.

    The scheduler is **not** started automatically — call
    ``scheduler.start()`` inside the FastAPI lifespan handler.
    """
    return BackgroundScheduler()
