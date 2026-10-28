"""Tests for should_run.py: does the menu job check at the right Davis times?"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scraper"))
import should_run  # noqa: E402

DAVIS = ZoneInfo("America/Los_Angeles")


def at(day, hour, minute):
    """A Davis time in the week of Sun Oct 25 – Sat Oct 31, 2026."""
    return datetime(2026, 10, day, hour, minute, tzinfo=DAVIS)


def yes(slot):
    return should_run.wanted(slot)[0]


def test_hourly_while_open():
    tue = 27
    assert all(yes(at(tue, h, 0)) for h in range(7, 22))     # 7 AM through 9 PM
    assert not yes(at(tue, 22, 0))                             # closed at 10 PM
    assert not yes(at(tue, 5, 0))


def test_every_30_minutes_in_the_last_hour_of_each_meal():
    tue = 27
    for h in (10, 16, 19, 21):        # breakfast ends 11, lunch 5 PM, Latitude 8 PM, dinner 10 PM
        assert yes(at(tue, h, 30))
    for h in (7, 8, 9, 11, 12, 13, 14, 15, 17, 18, 20):
        assert not yes(at(tue, h, 30))


def test_weekends_only_get_the_morning_check():
    sat, sun = 31, 25
    assert yes(at(sat, 6, 0)) and yes(at(sun, 6, 0))
    assert not yes(at(sat, 12, 0)) and not yes(at(sun, 10, 30))


def test_late_github_runs_still_count_for_the_right_slot():
    # The ":35" job meant for 10:30 AM Davis time (17:35 UTC in October) started 20 minutes late.
    slot = should_run.intended_slot(datetime(2026, 10, 27, 17, 55, tzinfo=timezone.utc), "35 0-5,13-23 * * *")
    assert (slot.hour, slot.minute) == (10, 30)
    # After daylight saving ends, 18:05 UTC is 10:00 AM in Davis.
    slot = should_run.intended_slot(datetime(2026, 12, 1, 18, 12, tzinfo=timezone.utc), "5 0-5,13-23 * * *")
    assert (slot.hour, slot.minute) == (10, 0)
