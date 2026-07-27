"""Trading-session resolution.

Regression cover for the price-blend bug: the midday scan took ~2h and straddled the
16:00 ET close, so `get_history` cached some tickers mid-session and some at the close
under one `date.today()` key. The post-close run then reused the blend (TTL 20h), and
results.json shipped prices that matched no single session — 10 of 12 sampled names
were off the real close, by up to 3.3%.

The fix is that a run resolves ONE session up front. These tests pin the boundaries.
"""
from datetime import date, datetime

import pytest

from engine.session import (
    MARKET_TZ,
    is_trading_day,
    previous_trading_day,
    resolve_session,
    session_is_current,
)


def et(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=MARKET_TZ)


@pytest.mark.parametrize("label,when,expected", [
    # The actual failure. These two timestamps are the start and end of one midday run
    # and MUST resolve differently, or they share a cache key and the blend returns.
    ("midday run start", et(2026, 7, 24, 14, 39), date(2026, 7, 23)),
    ("midday run end",   et(2026, 7, 24, 16, 51), date(2026, 7, 24)),
    ("post-close run",   et(2026, 7, 24, 17, 41), date(2026, 7, 24)),
    # Close boundary, including the settle margin.
    ("one min pre-close",  et(2026, 7, 24, 15, 59), date(2026, 7, 23)),
    ("inside settle",      et(2026, 7, 24, 16, 14), date(2026, 7, 23)),
    ("settle elapsed",     et(2026, 7, 24, 16, 15), date(2026, 7, 24)),
    # DST: a fixed-UTC cron fires 15:37 ET under EST, i.e. before the close. It must
    # report the prior session rather than label partial data as that day.
    ("EST early fire",     et(2026, 11, 17, 15, 37), date(2026, 11, 16)),
    ("EST after close",    et(2026, 11, 17, 16, 37), date(2026, 11, 17)),
    # Non-trading time: a morning review must see the last completed session.
    ("saturday",           et(2026, 7, 25, 9, 0),  date(2026, 7, 24)),
    ("sunday",             et(2026, 7, 26, 9, 0),  date(2026, 7, 24)),
    ("monday pre-open",    et(2026, 7, 27, 7, 0),  date(2026, 7, 24)),
    # Holidays skip backwards (Thanksgiving 2026-11-26).
    ("day after holiday",  et(2026, 11, 27, 7, 0), date(2026, 11, 25)),
])
def test_resolve_session(label, when, expected):
    assert resolve_session(when) == expected, label


def test_midday_and_postclose_never_share_a_session():
    """The invariant the cache depends on."""
    start = resolve_session(et(2026, 7, 24, 14, 39))
    end = resolve_session(et(2026, 7, 24, 17, 41))
    assert start != end


def test_run_duration_cannot_change_the_session():
    """Any two moments that resolve to the same session produce the same key, so a
    slow run stays internally consistent."""
    moments = [et(2026, 7, 24, h, m) for h, m in [(17, 0), (18, 30), (20, 15), (23, 59)]]
    assert len({resolve_session(t) for t in moments}) == 1


def test_session_override(monkeypatch):
    monkeypatch.setenv("SESSION_DATE", "2026-03-04")
    assert resolve_session() == date(2026, 3, 4)


def test_session_is_current():
    now = et(2026, 7, 24, 17, 41)
    assert session_is_current(date(2026, 7, 24), now)
    assert not session_is_current(date(2026, 7, 23), now)


def test_trading_day_helpers():
    assert not is_trading_day(date(2026, 7, 25))      # Saturday
    assert not is_trading_day(date(2026, 11, 26))     # Thanksgiving
    assert is_trading_day(date(2026, 7, 24))
    assert previous_trading_day(date(2026, 7, 27)) == date(2026, 7, 24)
