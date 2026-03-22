"""Tests for APScheduler factory — src/lib/scheduler.py."""

from apscheduler.schedulers.background import BackgroundScheduler

from src.lib.scheduler import create_scheduler


class TestCreateScheduler:
    """Verify scheduler factory returns a properly configured scheduler."""

    def test_returns_background_scheduler(self):
        scheduler = create_scheduler()
        assert isinstance(scheduler, BackgroundScheduler)

    def test_scheduler_is_not_running_on_creation(self):
        scheduler = create_scheduler()
        assert not scheduler.running
